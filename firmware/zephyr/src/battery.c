#include "battery.h"

#include <zephyr/drivers/adc.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#include "board_io.h"

LOG_MODULE_REGISTER(battery, LOG_LEVEL_INF);

/* Channels are optional per board (devicetree io-channel-names): Rev A pod has VBAT only, the dev
 * kit has both, the bench controller has none (USB powered). */
#define HAVE_VBAT (OP_HAS_ADC(vbat) && IS_ENABLED(CONFIG_OPENPATCH_BATTERY_MONITOR))
#define HAVE_VMOT OP_HAS_ADC(vmot)

#if HAVE_VBAT
static const struct adc_dt_spec g_vbat = ADC_DT_SPEC_GET_BY_NAME(OP_ZU, vbat);
#endif
#if HAVE_VMOT
static const struct adc_dt_spec g_vmot = ADC_DT_SPEC_GET_BY_NAME(OP_ZU, vmot);
#endif

#if HAVE_VBAT || HAVE_VMOT
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
#endif

int battery_init(void)
{
    int rc = 0;
#if HAVE_VBAT
    if (!adc_is_ready_dt(&g_vbat)) return -ENODEV;
    rc = adc_channel_setup_dt(&g_vbat);
#endif
#if HAVE_VMOT
    if (!rc) {
        if (!adc_is_ready_dt(&g_vmot)) return -ENODEV;
        rc = adc_channel_setup_dt(&g_vmot);
    }
#endif
    if (!IS_ENABLED(CONFIG_OPENPATCH_BATTERY_MONITOR)) LOG_WRN("battery monitoring disabled (USB-powered board)");
    return rc;
}

uint16_t battery_vbat_mv(void)
{
    if (IS_ENABLED(CONFIG_OPENPATCH_SIM_BATTERY)) return (uint16_t)CONFIG_OPENPATCH_SIM_BATTERY_MV;
#if HAVE_VBAT
    return read_scaled_mv(&g_vbat);
#else
    return 0xFFFF; /* unreachable in practice: no VBAT channel means no battery hook */
#endif
}

bool battery_vmot_available(void) { return HAVE_VMOT; }

uint16_t battery_vmot_mv(void)
{
#if HAVE_VMOT
    return read_scaled_mv(&g_vmot);
#else
    return 0;
#endif
}
