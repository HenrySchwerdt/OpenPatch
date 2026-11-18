/*
 * Devicetree access helpers. Every pin of the pod is a property of the /zephyr,user node
 * (board dts or app overlay); C code never contains a pin number. A feature whose property
 * is missing is compiled out (dev kit without safety latch, charger, ...).
 */
#ifndef BOARD_IO_H
#define BOARD_IO_H

#include <zephyr/devicetree.h>

#define OP_ZU DT_PATH(zephyr_user)
#define OP_HAS(prop) DT_NODE_HAS_PROP(OP_ZU, prop)

#endif
