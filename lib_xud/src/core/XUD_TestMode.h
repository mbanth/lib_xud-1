// Copyright (c) 2011-2020, XMOS Ltd, All rights reserved
#ifndef __XUD_TESTMODE_H__
#define __XUD_TESTMODE_H__

#include <xs1.h>

#include "XUD_HAL.h"
#include "XUD_USB_Defines.h"

unsigned UsbTestModeHandler_asm();
unsigned XUD_UsbTestSE0();

int XUD_TestMode_TestJ () ;
int XUD_TestMode_TestK () ;
int XUD_TestMode_TestSE0NAK () ;
int XUD_TestMode_TestPacket () ;

#endif
