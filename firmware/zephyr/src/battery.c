#include "battery.h"

#include <zephyr/drivers/adc.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#include "board_io.h"

LOG_MODULE_REGISTER(battery, LOG_LEVEL_INF);

static const struct adc_dt_spec g_vbat = ADC_DT_SPEC_GET_BY_NAME(OP_ZU, vbat);
static const struct adc_dt_spec g_vmot = ADC_DT_SPEC_GET_BY_NAME(OP_ZU, vmot);

int battery_init(void)
{
    if (!adc_is_ready_dt(&g_vbat) || !adc_is_ready_dt(&g_vmot)) return -ENODEV;
    int rc = adc_channel_setup_dt(&g_vbat);
    if (!rc) rc = adc_channel_setup_dt(&g_vmot);
    return rc;
}

static uint16_t read_scaled_mv(const struct adc_dt_spec *ch)
{
    int16_t raw = 0;
    struct adc_sequence seq = {.buffer = &raw, .buffer_size = sizeof raw};
    int32_t mv;
    if (adc_sequence_init_dt(ch, &seq) != 0 || adc_read_dt(ch, &seq) != 0) return 0;
    mv = raw;
    if (adc_raw_to_millivolts_dt(ch, &mv) != 0 || mv < 0) return 0;
    int64_t v = (int64_t)mv * CONFIG_OPENPATCH_VBAT_DIV_NUM / CONFIG_OPENPATCH_VBAT_DIV_DEN;
    return v > UINT16_MAX ? UINT16_MAX : (uint16_t)v;
}

uint16_t battery_vbat_mv(void)
{
    if (IS_ENABLED(CONFIG_OPENPATCH_SIM_BATTERY)) return (uint16_t)CONFIG_OPENPATCH_SIM_BATTERY_MV;
    return read_scaled_mv(&g_vbat);
}

uint16_t battery_vmot_mv(void) { return read_scaled_mv(&g_vmot); }
