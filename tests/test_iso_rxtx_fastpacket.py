#!/usr/bin/env python
# Copyright 2016-2021 XMOS LIMITED.
# This Software is subject to the terms of the XMOS Public Licence: Version 1.

import xmostest
from usb_packet import *
import usb_packet
from helpers import do_usb_test, RunUsbTest
from usb_session import UsbSession
from usb_transaction import UsbTransaction


def do_test(arch, clk, phy, usb_speed, seed, verbose=False):

    ep = 3
    address = 1
    start_length = 10
    end_length = 19

    session = UsbSession(
        bus_speed=usb_speed, run_enumeration=False, device_address=address
    )

    for pktLength in range(start_length, end_length + 1):

        # < 17 fails
        session.add_event(
            UsbTransaction(
                session,
                deviceAddress=address,
                endpointNumber=ep,
                endpointType="ISO",
                direction="OUT",
                dataLength=pktLength,
                interEventDelay=20,
            )
        )

        session.add_event(
            UsbTransaction(
                session,
                deviceAddress=address,
                endpointNumber=ep,
                endpointType="ISO",
                direction="IN",
                dataLength=pktLength,
                interEventDelay=58,
            )
        )

    do_usb_test(
        arch,
        clk,
        phy,
        usb_speed,
        [session],
        __file__,
        seed,
        level="smoke",
        extra_tasks=[],
        verbose=verbose,
    )


def runtest():
    RunUsbTest(do_test)
