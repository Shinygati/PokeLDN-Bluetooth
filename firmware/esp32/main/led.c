/* The LED: LEDC PWM on GPIO2 (classic ESP32; GPIO17 in the E32R40T build), GPIO21 (XIAO ESP32S3; none in
   the SZPI build, whose GPIO48 is a WS2812) or GPIO15 (XIAO ESP32C6),
   recomputed every 10 ms by a priority-1 task on the last core, below the wire tasks (19 to 21).
   It reads counters the radio already keeps. docs/hardware_esp32.md, The board's LED and buttons. */
#include <math.h>
#include <stdbool.h>

#include "driver/gpio.h"
#include "driver/ledc.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "led.h"
#include "esp_log.h"
#ifdef POKELDN_RGB_GPIO
#include "driver/spi_master.h"
#include "esp_rom_sys.h"
static spi_device_handle_t rgb_device;
static void rgb_write(uint32_t color)
{
    if (!rgb_device) return;
    static uint32_t previous_color = 0xffffffff;
    if (color == previous_color) return;
    /* 2.5 MHz: WS2812 zero=100 (0.4/0.8 us), one=110 (0.8/0.4 us).
       Polling avoids the RMT completion interrupt that times out on this build. */
    uint8_t waveform[49] = {0};
    for (unsigned i = 0; i < 24; ++i) {
        unsigned symbol = (color & (1u << (23-i))) ? 6 : 4;
        for (unsigned j = 0; j < 3; ++j) {
            unsigned bit = i*3+j;
            if (symbol & (1u << (2-j))) waveform[bit/8] |= 1u << (7-bit%8);
        }
    }
    /* The trailing zero bytes end with MOSI low; keep it low for the latch. */
    spi_transaction_t transfer = {.length = sizeof(waveform)*8, .tx_buffer = waveform};
    esp_err_t err = spi_device_polling_transmit(rgb_device, &transfer);
    esp_rom_delay_us(320);
    if (err == ESP_OK) previous_color = color;
    static esp_err_t last_error = ESP_OK;
    if (err != last_error) ESP_LOGW("rgb", "SPI LED transfer: %s", esp_err_to_name(err));
    last_error = err;
}
static void rgb_show(bool connected, bool distributing, int64_t now)
{
    uint32_t color = (connected || distributing) ? 5u << 16 : 5u << 8; /* GRB, ~2% */
    if (distributing && (now / 1000) % 2) color = 0;
    rgb_write(color);
}
#endif

#if CONFIG_IDF_TARGET_ESP32 && defined(POKELDN_DISPLAY_E32R40T)
#define LED_GPIO 17     /* the E32R40T's blue RGB LED, lit while low: GPIO2 is its LCD's DC */
#define LED_INVERT 1
#elif CONFIG_IDF_TARGET_ESP32
#define LED_GPIO 2
#define LED_INVERT 0
#elif CONFIG_IDF_TARGET_ESP32S3 && !defined(POKELDN_DISPLAY_SZPI)
#define LED_GPIO 21     /* the XIAO ESP32S3's yellow LED, lit while low */
#define LED_INVERT 1
#elif CONFIG_IDF_TARGET_ESP32C6
#define LED_GPIO 15     /* the XIAO ESP32C6's yellow LED, lit while low */
#define LED_INVERT 1
#endif
#if CONFIG_IDF_TARGET_ESP32C3 || CONFIG_IDF_TARGET_ESP32C6
#define BUTTON_GPIO 9
#elif CONFIG_IDF_TARGET_ESP32 || CONFIG_IDF_TARGET_ESP32S3
#define BUTTON_GPIO 0   /* BOOT: low while pressed, pulled up */
#endif
#define BUTTON_TICKS 3  /* 30 ms of one level makes it the button's state */
#define DUTY_MAX 8191   /* 13 bits at 5 kHz */
#define TICK_MS 10
#ifdef POKELDN_RGB_GPIO
#undef LED_GPIO
#endif
#define CROSSFADE_MS 150

static const uint16_t DEFAULT_PERIOD_MS[LED_PATTERNS] = {
    [LED_BREATHE] = 3000, [LED_BLINK] = 1000, [LED_FLASH3] = 1000, [LED_RAMP_UP] = 1000,
    [LED_RAMP_DOWN] = 1000, [LED_PULSE] = 1200,
};

static portMUX_TYPE s_lock = portMUX_INITIALIZER_UNLOCKED;
static led_look_t s_host = {LED_PULSE, 255, 900};   /* the boot pulse */
static int64_t s_host_until_ms = 900;               /* 0: held until the next command */
static uint32_t s_host_serial = 1;                  /* restarts the look when the host resends it */
static led_state_t s_state;
static led_button_t s_button;

static int64_t now_ms(void) { return esp_timer_get_time() / 1000; }

static float clamp01(float x) { return x < 0 ? 0 : x > 1 ? 1 : x; }
static float smooth(float x) { x = clamp01(x); return x * x * (3 - 2 * x); }
static float ease_in_out(float x)
{
    x = clamp01(x);
    return x < 0.5f ? 4 * x * x * x : 1 - powf(2 - 2 * x, 3) / 2;
}

/* A soft square: on over [0, width) with eased edges `edge` long, off after. */
static float soft_on(float p, float width, float edge)
{
    return p < width ? fminf(smooth(p / edge), smooth((width - p) / edge)) : 0;
}

/* Brightness 0..1 of a pattern `t` ms into it. */
static float level(const led_look_t *look, int64_t t)
{
    const float period = look->period_ms ? look->period_ms : DEFAULT_PERIOD_MS[look->pattern];
    const float p = period > 0 ? fmodf((float)t, period) / period : 0;
    const float once = period > 0 ? (float)t / period : 1;
    switch (look->pattern) {
    case LED_ON: return 1;
    case LED_BREATHE: return 0.5f - 0.5f * cosf(2 * (float)M_PI * p);
    case LED_BLINK: return soft_on(p, 0.5f, 0.08f);
    case LED_FLASH3: {
        const float slot = p / 0.2f;
        return slot < 3 ? soft_on(slot - floorf(slot), 0.5f, 0.1f) : 0;
    }
    case LED_RAMP_UP: return ease_in_out(once);
    case LED_RAMP_DOWN: return 1 - ease_in_out(once);
    case LED_PULSE: return p < 0.15f ? 1 - powf(1 - p / 0.15f, 2) : powf(1 - (p - 0.15f) / 0.85f, 3);
    default: return 0;
    }
}

static bool same_look(const led_look_t *a, const led_look_t *b)
{
    return a->pattern == b->pattern && a->peak == b->peak && a->period_ms == b->period_ms;
}

static void led_task(void *arg)
{
#ifdef POKELDN_RGB_GPIO
    /* Visible proof that this driver owns the pixel: off, red, off, green, off, blue, off. */
    const uint32_t startup[] = {0, 5u << 8, 0, 5u << 16, 0, 5u, 0};
    for (unsigned i = 0; i < sizeof(startup) / sizeof(startup[0]); ++i) {
        rgb_write(startup[i]);
        vTaskDelay(pdMS_TO_TICKS(700));
    }
#endif
    led_look_t shown = {LED_OFF, 0, 0};
    int64_t look_started = now_ms(), fade_started = look_started;
    float fade_from = 0, output = 0, flash = 0, press_flash = 0;
    bool pressed = false;
    int same_level = 0, last_level = 1;
    uint32_t presses = 0;
    uint32_t last_activity = 0, last_alarm = 0, last_serial = 0;
    int64_t alarm_until = 0;
    TickType_t wake = xTaskGetTickCount();
    for (;;) {
        const int64_t now = now_ms();
#ifdef BUTTON_GPIO
        const int button_level = gpio_get_level(BUTTON_GPIO);
#else
        const int button_level = 1;   /* Generic new targets do not assume board-specific wiring. */
#endif
        same_level = button_level == last_level ? same_level + 1 : 0;
        last_level = button_level;
        if (same_level == BUTTON_TICKS && pressed != (button_level == 0)) {
            pressed = button_level == 0;
            if (pressed) {
                press_flash = 1;
                if (s_button) s_button(++presses, esp_timer_get_time());
            }
        }
        led_look_t look, host;
        uint32_t serial;
        taskENTER_CRITICAL(&s_lock);
        if (s_host.pattern != LED_AUTO && s_host_until_ms && now >= s_host_until_ms)
            s_host.pattern = LED_AUTO;
        host = s_host;
        serial = s_host_serial;
        taskEXIT_CRITICAL(&s_lock);

        uint32_t activity = last_activity, alarm = last_alarm;
        led_look_t automatic = {LED_OFF, 0, 0};
        if (s_state) s_state(&automatic, &activity, &alarm);
        if (alarm != last_alarm) alarm_until = now + 1500;
        last_alarm = alarm;

        const bool is_auto = host.pattern == LED_AUTO;
        if (!is_auto) look = host;
        else if (now < alarm_until) look = (led_look_t){LED_FLASH3, 255, 750};
        else look = automatic;
        if (!same_look(&look, &shown) || serial != last_serial) {
            fade_from = output;
            fade_started = look_started = now;
            shown = look;
            last_serial = serial;
        }
        const float target = level(&shown, now - look_started) * shown.peak / 255.0f;
        const float mix = smooth((float)(now - fade_started) / CROSSFADE_MS);
        output = fade_from + (target - fade_from) * mix;

        /* A flicker per frame, retriggered only once the last has faded: a flood reads as a fast
           shimmer rather than a steady light. */
        if (is_auto && activity != last_activity && flash < 0.25f) flash = 1;
        last_activity = activity;
        /* A press answers with a full flash over any look, so the player sees it was taken. */
        const float shown_level = fmaxf(fmaxf(output, is_auto ? flash * 0.7f : 0), press_flash);
#ifdef POKELDN_RGB_GPIO
        rgb_show(automatic.pattern != LED_OFF, automatic.pattern == LED_BLINK, now);
#endif
        flash *= 0.8f;
        press_flash *= 0.9f;

#ifdef LED_GPIO
        ledc_set_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0,
                      (uint32_t)lroundf(powf(clamp01(shown_level), 2.2f) * DUTY_MAX));
        ledc_update_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0);
#else
        (void)shown_level;   /* C3 LED wiring varies; keep BOOT markers active. */
#endif
        vTaskDelayUntil(&wake, pdMS_TO_TICKS(TICK_MS));
    }
}

bool led_set(uint8_t pattern, uint8_t peak, uint16_t period_ms, uint16_t duration_ms)
{
    if (pattern >= LED_PATTERNS) return false;
    const int64_t until = duration_ms ? now_ms() + duration_ms : 0;
    taskENTER_CRITICAL(&s_lock);
    s_host = (led_look_t){pattern, peak, period_ms};
    s_host_until_ms = until;
    ++s_host_serial;
    taskEXIT_CRITICAL(&s_lock);
    return true;
}

void led_start(led_state_t state, led_button_t button)
{
    s_state = state;
    s_button = button;
#ifdef POKELDN_RGB_GPIO
    const spi_bus_config_t bus = {.mosi_io_num = POKELDN_RGB_GPIO,
        .miso_io_num = -1, .sclk_io_num = -1, .quadwp_io_num = -1,
        .quadhd_io_num = -1, .max_transfer_sz = 49};
    const spi_device_interface_config_t device = {.clock_speed_hz = 2500000,
        .mode = 0, .spics_io_num = -1, .queue_size = 1};
    esp_err_t rgb_error = spi_bus_initialize(SPI2_HOST, &bus, SPI_DMA_DISABLED);
    if (rgb_error == ESP_OK) rgb_error = spi_bus_add_device(SPI2_HOST, &device, &rgb_device);
    ESP_LOGW("rgb", "GPIO%d GRB SPI polling init: %s", POKELDN_RGB_GPIO, esp_err_to_name(rgb_error));
    if (rgb_error != ESP_OK) rgb_device = NULL;
#endif
#ifdef BUTTON_GPIO
    const gpio_config_t input = {
        .pin_bit_mask = 1ULL << BUTTON_GPIO, .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE, .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&input);
#endif
#ifdef LED_GPIO
    const ledc_timer_config_t timer = {
        .speed_mode = LEDC_LOW_SPEED_MODE, .duty_resolution = LEDC_TIMER_13_BIT,
        .timer_num = LEDC_TIMER_0, .freq_hz = 5000, .clk_cfg = LEDC_AUTO_CLK,
    };
    const ledc_channel_config_t channel = {
        .gpio_num = LED_GPIO, .speed_mode = LEDC_LOW_SPEED_MODE, .channel = LEDC_CHANNEL_0,
        .timer_sel = LEDC_TIMER_0, .duty = 0, .hpoint = 0, .flags.output_invert = LED_INVERT,
    };
    /* A board without the LED still runs: the radio never depends on it. */
    if (ledc_timer_config(&timer) != ESP_OK || ledc_channel_config(&channel) != ESP_OK) return;
#endif
    s_host_until_ms = now_ms() + 900;
    if (xTaskCreatePinnedToCore(led_task, "led", 4096, NULL, 1, NULL, configNUMBER_OF_CORES - 1) != pdPASS)
        ESP_LOGE("rgb", "LED task creation failed");
}
