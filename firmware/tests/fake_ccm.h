/* TEST-ONLY fake AES-CCM (XOR keystream + FNV tag). NOT SECURE. */
#ifndef FAKE_CCM_H
#define FAKE_CCM_H
#include "op/openpatch_proto.h"
typedef struct { int accepted_calls; uint16_t last_seq; } fake_ccm_ctx_t;
extern fake_ccm_ctx_t fake_ccm_ctx;
extern const op_ccm_ops_t fake_ccm_ops;
#endif
