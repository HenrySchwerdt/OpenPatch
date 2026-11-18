#include "buzzer.h"

#include <zephyr/device.h>
#include <zephyr/drivers/pwm.h>
#include <zephyr/kernel.h>

static const struct device *const g_pwm = DEVICE_DT_GET(DT_ALIAS(pwm_buzzer));

#define TONE_PERIOD_NS 250000u /* 4 kHz piezo resonance */
#define BEEP_MS 120
#define ALARM_ON_MS 250
#define ALARM_OFF_MS 400

static struct k_work_delayable g_work;
static op_buzzer_t g_pattern;
static bool g_on;
static bool g_silenced;

static void tone(bool on)
{
    g_on = on;
    pwm_set(g_pwm, 0, TONE_PERIOD_NS, on ? TONE_PERIOD_NS / 2 : 0, 0);
}

static void work_fn(struct k_work *w)
{
    ARG_UNUSED(w);
    if (g_pattern == OP_BUZZER_BEEP) {
        tone(false);
        g_pattern = OP_BUZZER_OFF;
    } else if (g_pattern == OP_BUZZER_ALARM) {
        if (g_on || g_silenced) {
            tone(false);
            k_work_schedule(&g_work, K_MSEC(ALARM_OFF_MS));
        } else {
            tone(true);
            k_work_schedule(&g_work, K_MSEC(ALARM_ON_MS));
        }
    }
}

int buzzer_init(void)
{
    if (!device_is_ready(g_pwm)) return -ENODEV;
    k_work_init_delayable(&g_work, work_fn);
    tone(false);
    return 0;
}

void buzzer_set(op_buzzer_t pattern)
{
    if (pattern == g_pattern && pattern == OP_BUZZER_ALARM) return; /* alarm is already running */
    if (pattern != OP_BUZZER_ALARM) g_silenced = false;
    k_work_cancel_delayable(&g_work);
    g_pattern = pattern;
    switch (pattern) {
    case OP_BUZZER_OFF: tone(false); break;
    case OP_BUZZER_BEEP:
        tone(true);
        k_work_schedule(&g_work, K_MSEC(BEEP_MS));
        break;
    case OP_BUZZER_ALARM:
        g_silenced = false;
        tone(true);
        k_work_schedule(&g_work, K_MSEC(ALARM_ON_MS));
        break;
    }
}

void buzzer_silence(void)
{
    if (g_pattern == OP_BUZZER_ALARM) {
        g_silenced = true;
        tone(false);
    }
}
