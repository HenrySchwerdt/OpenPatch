#include "current_sense.h"

#include <zephyr/drivers/adc.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#include "board_io.h"

LOG_MODULE_REGISTER(isense, LOG_LEVEL_INF);

#if OP_HAS_ADC(imot)

static const struct adc_dt_spec g_imot = ADC_DT_SPEC_GET_BY_NAME(OP_ZU, imot);

#define SAMPLER_STACK 1024
#define SAMPLER_PRIO 5

static K_SEM_DEFINE(g_go, 0, 1);
static K_SEM_DEFINE(g_stopped, 0, 1);
static volatile bool g_active;
static op_motor_stats_t g_last;

/* running burst, owned by the sampler thread while g_active */
static uint32_t g_sum_ma;
static uint32_t g_n;
static uint16_t g_peak_ma;

static uint16_t sample_ma(void)
{
    int16_t raw = 0;
    struct adc_sequence seq = {.buffer = &raw, .buffer_size = sizeof raw};
    int32_t mv;
    if (adc_sequence_init_dt(&g_imot, &seq) != 0 || adc_read_dt(&g_imot, &seq) != 0) return 0;
    mv = raw;
    if (adc_raw_to_millivolts_dt(&g_imot, &mv) != 0 || mv < 0) return 0;
    /* mA = mV * 1000 / (mV per A of the sense path), e.g. 1 ohm = 1000 mV/A */
    int64_t ma = (int64_t)mv * 1000 / CONFIG_OPENPATCH_IMOT_MV_PER_A;
    return ma > UINT16_MAX ? UINT16_MAX : (uint16_t)ma;
}

static void sampler(void *a, void *b, void *c)
{
    ARG_UNUSED(a);
    ARG_UNUSED(b);
    ARG_UNUSED(c);
    for (;;) {
        k_sem_take(&g_go, K_FOREVER);
        while (g_active) {
            uint16_t ma = sample_ma();
            g_sum_ma += ma;
            g_n++;
            if (ma > g_peak_ma) g_peak_ma = ma;
        }
        k_sem_give(&g_stopped);
    }
}

K_THREAD_DEFINE(isense_thread, SAMPLER_STACK, sampler, NULL, NULL, NULL, SAMPLER_PRIO, 0, 0);

int current_sense_init(void)
{
    if (!adc_is_ready_dt(&g_imot)) return -ENODEV;
    return adc_channel_setup_dt(&g_imot);
}

bool current_sense_available(void) { return true; }

void current_sense_begin(void)
{
    g_sum_ma = 0;
    g_n = 0;
    g_peak_ma = 0;
    k_sem_reset(&g_stopped);
    g_active = true;
    k_sem_give(&g_go);
}

void current_sense_end(void)
{
    g_active = false;
    /* the sampler finishes its current conversion (well under 1 ms) and signals */
    if (k_sem_take(&g_stopped, K_MSEC(50)) != 0) {
        LOG_ERR("current sampler did not stop");
        g_last = (op_motor_stats_t){0};
        return;
    }
    g_last.samples = g_n > UINT16_MAX ? UINT16_MAX : (uint16_t)g_n;
    g_last.peak_ma = g_peak_ma;
    g_last.mean_ma = g_n ? (uint16_t)(g_sum_ma / g_n) : 0;
}

bool current_sense_stats(op_motor_stats_t *out)
{
    *out = g_last;
    return true;
}

#else

int current_sense_init(void) { return 0; }
bool current_sense_available(void) { return false; }
void current_sense_begin(void) {}
void current_sense_end(void) {}
bool current_sense_stats(op_motor_stats_t *out)
{
    ARG_UNUSED(out);
    return false;
}

#endif
