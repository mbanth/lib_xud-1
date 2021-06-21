# Copyright 2016-2021 XMOS LIMITED.
# This Software is subject to the terms of the XMOS Public Licence: Version 1.
""" Define packet types

Packet Class Hierarchy
----------------------

+-----------+
|   Object  |
+-----------+
      ^
      |
+-----------+
| UsbPacket |
+-----------+
      ^
      |       +------------+
      |-------| DataPacket |
      |       +------------+
      |
      |       +-----------------+
      |-------| HandshakePacket |
      |       +-----------------+
      |
      |       +----------+
      |-------| RxPacket |
      |       +----------+
      |
      |       +----------+
      --------| TxPacket |
              +----------+
                   ^
                   |
            +-------------+
            | TokenPacket |
            +-------------+

+----------+   +------------+   +----------+
| RxPacket |   | DataPacket |   | TxPacket |
+----------+   +------------+   +----------+
      ^           ^      ^            ^
      |           |      |            |
      -------------      --------------
            |                  |
     +--------------+   +--------------+
     | RxDataPacket |   | TxDataPacket |
     +--------------+   +--------------+

+----------+   +-----------------+   +----------+
| RxPacket |   | HandshakePacket |   | TxPacket |
+----------+   +-----------------+   +----------+
      ^           ^           ^            ^
      |           |           |            |
      -------------           --------------
            |                       |
  +-------------------+   +-------------------+
  | RxHandshakePacket |   | TxHandshakePacket |
  +-------------------+   +-------------------+
"""

from usb_event import UsbEvent
import usb_phy


USB_DATA_VALID_COUNT = {"FS": 39, "HS": 0}

# In USB clocks
RXA_END_DELAY = 2  # Pad delay not currently simulated in xsim for USB or OTP, so add this delay here
RXA_START_DELAY = 5  # Taken from RTL sim

# TODO shoud we have a PID class?
# TODO remove the inverted check bits
USB_PID = {
    "OUT": 0xE1,
    "ACK": 0xD2,
    "DATA0": 0xC3,
    "PING": 0xB4,
    "SOF": 0xA5,
    "DATA1": 0x4B,
    "IN": 0x69,
    "NAK": 0x5A,
    "SETUP": 0x2D,
    "STALL": 0x1E,
    "RESERVED": 0x0F,
}


def CreateSofToken(frameNumber, badCrc=False, interEventDelay=1000):
    ep = (frameNumber >> 7) & 0xF
    address = (frameNumber) & 0x7F

    if badCrc:
        return TokenPacket(
            pid=USB_PID["SOF"],
            address=address,
            endpoint=ep,
            crc5=0xFF,
            interEventDelay=interEventDelay,
        )
    else:
        return TokenPacket(
            pid=USB_PID["SOF"],
            address=address,
            endpoint=ep,
            interEventDelay=interEventDelay,
        )


def reflect(val, numBits):

    valRef = 0
    for i in range(numBits):
        valRef <<= 1

        if val & 1:
            valRef |= 1

        val >>= 1

    return valRef


def GenCrc16(args):

    data = args

    crc = 0xFFFF
    poly = 0x8005

    for byte in data:
        topBit = 1 << 15
        crc ^= reflect(int(byte) & int(0xFF), 8) << 8

        for k in range(0, 8):
            if crc & topBit:
                crc = (crc << 1) ^ poly
            else:
                crc <<= 1

    # //crc = crc ^0xffff;
    crc = reflect(crc, 16)
    crc = ~crc
    crc = crc & 0xFFFF
    # print "CRC: : {0:#x}".format(crc)
    return crc


def GenCrc5(args):
    intSize = 32
    elevenBits = args

    poly5 = 0x05 << (intSize - 5)
    crc5 = 0x1F << (intSize - 5)
    udata = elevenBits << (intSize - 11)
    # crc over 11 bits

    iBitcnt = 11

    while iBitcnt > 0:
        if (udata ^ crc5) & (0x1 << (intSize - 1)):  # bit4 != bit4?
            crc5 <<= 1
            crc5 ^= poly5
        else:
            crc5 <<= 1
        udata <<= 1
        iBitcnt = iBitcnt - 1

    # Shift back into position
    crc5 >>= intSize - 5

    # Invert contents to generate crc field
    crc5 ^= 0x1F

    crc5 = reflect(crc5, 5)
    return crc5


# Functions for creating the data contents of packets
def create_data(args):
    f_name, f_args = args
    func = "create_data_{}".format(f_name)
    return globals()[func](f_args)


def create_data_step(args):
    step, num_data_bytes = args
    return [(step * i) & 0xFF for i in range(num_data_bytes)]


def create_data_same(args):
    value, num_data_bytes = args
    return [value & 0xFF for i in range(num_data_bytes)]


# Functions for creating the expected output that the DUT will print given
# this packet
def create_data_expect(args):
    f_name, f_args = args
    func = "create_data_expect_{}".format(f_name)
    return globals()[func](f_args)


def create_data_expect_step(args):
    step, num_data_bytes = args
    return "Step = {0}\n".format(step)


def create_data_expect_same(args):
    value, num_data_bytes = args
    return "Value = {0}\n".format(value)


class BusReset(object):
    def __init__(self, **kwargs):
        self.duration_ms = kwargs.pop("duraton", 10)  # Duration of reset
        self.bus_speed = kwargs.pop("bus_speed", "high")  # Bus speed to reset into


# Lowest base class for all packets. All USB packets have:
# - a PID
# - some (or none) data bytes
class UsbPacket(UsbEvent):
    def __init__(self, **kwargs):
        self.pid = kwargs.pop("pid", 0xC3)
        self.data_bytes = kwargs.pop("data_bytes", None)
        self.num_data_bytes = kwargs.pop("length", 0)
        self.bad_crc = kwargs.pop("bad_crc", False)
        ied = kwargs.pop("interEventDelay", None)
        super(UsbPacket, self).__init__(interEventDelay=ied)

    @property
    def event_count(self):
        return 1

    def __str__(self):
        return super().__str__() + " USBPacket"

    def get_pid_str(self):
        for key, value in USB_PID.items():
            if value == self.pid:
                return key
        return "UNKNOWN"


# Rx to host i.e. xCORE Tx
class RxPacket(UsbPacket):
    def __init__(self, **kwargs):
        self._timeout = kwargs.pop(
            "timeout", usb_phy.USB_PKT_TIMINGS["TX_TO_RX_PACKET_TIMEOUT"]
        )
        super(RxPacket, self).__init__(**kwargs)

    @property
    def timeout(self):
        return self._timeout

    def expected_output(self, bus_speed, offset=0):
        expected_output = "Packet:\tDEVICE -> HOST\n"

        for (i, byte) in enumerate(self.get_bytes()):
            expected_output += "\tRX byte: {0:#x}\n".format(byte)

        return expected_output

    def drive(self, usb_phy, bus_speed):

        wait = usb_phy.wait
        xsi = usb_phy.xsi

        timeout = self.timeout
        in_rx_packet = False
        rx_packet = []

        while timeout != 0:

            wait(lambda x: usb_phy._clock.is_high())
            wait(lambda x: usb_phy._clock.is_low())

            timeout = timeout - 1

            # sample TXV for new packet
            if xsi.sample_port_pins(usb_phy._txv) == 1:
                print("Packet:\tDEVICE -> HOST")
                in_rx_packet = True
                break

        if in_rx_packet == False:
            print("ERROR: Timed out waiting for packet")
        else:
            while in_rx_packet == True:

                # TODO txrdy pulsing
                xsi.drive_port_pins(usb_phy._txrdy, 1)
                data = xsi.sample_port_pins(usb_phy._txd)

                print("\tRX byte: {0:#x}".format(data))
                rx_packet.append(data)

                wait(lambda x: usb_phy._clock.is_high())
                wait(lambda x: usb_phy._clock.is_low())

                if xsi.sample_port_pins(usb_phy._txv) == 0:
                    # TxV low, break out of loop
                    in_rx_packet = False

            # End of packet
            xsi.drive_port_pins(usb_phy._txrdy, 0)

            # Check packet against expected
            expected = self.get_bytes(do_tokens=False)
            if len(expected) != len(rx_packet):
                print(
                    "ERROR: Rx packet length bad. Expecting: {} actual: {}".format(
                        len(expected), len(rx_packet)
                    )
                )

            # Check packet data against expected
            if expected != rx_packet:
                print("ERROR: Rx Packet Error. Expected:")
                for item in expected:
                    print("{0:#x}".format(item))

                print("Received:")
                for item in rx_packet:
                    print("{0:#x}".format(item))


# Tx from host i.e. xCORE Rx
class TxPacket(UsbPacket):
    def __init__(self, **kwargs):
        self.rxa_start_delay = kwargs.pop("rxa_start_delay", 2)
        self.rxa_end_delay = kwargs.pop("rxa_end_delay", RXA_END_DELAY)
        self.rxe_assert_time = kwargs.pop("rxe_assert_time", 0)
        self.rxe_assert_length = kwargs.pop("rxe_assert_length", 1)

        ied = kwargs.pop(
            "interEventDelay", usb_phy.USB_PKT_TIMINGS["TX_TO_TX_PACKET_DELAY"]
        )
        super(TxPacket, self).__init__(**kwargs, interEventDelay=ied)

    def expected_output(self, bus_speed, offset=0):
        expected_output = "Packet:\tHOST -> DEVICE\n"
        expected_output += "\tPID: {} ({:#x})\n".format(self.get_pid_str(), self.pid)
        return expected_output

    def drive(self, usb_phy, bus_speed, verbose=True):

        xsi = usb_phy.xsi
        wait = usb_phy.wait

        # xCore should not be trying to send if we are trying to send..
        if xsi.sample_port_pins(usb_phy._txv) == 1:
            print("ERROR: Unexpected packet from xCORE (TxPacket 0)")

        rxv_count = USB_DATA_VALID_COUNT[bus_speed]

        usb_phy.wait_for_clocks(self.interEventDelay)

        print(
            "Packet:\tHOST -> DEVICE\n\tPID: {0} ({1:#x})".format(
                self.get_pid_str(), self.pid
            )
        )

        # Set RXA high to USB shim
        xsi.drive_periph_pin(usb_phy._rxa, 1)

        # Wait for RXA start delay
        rxa_start_delay = RXA_START_DELAY

        while rxa_start_delay != 0:
            wait(lambda x: usb_phy._clock.is_high())
            wait(lambda x: usb_phy._clock.is_low())
            rxa_start_delay = rxa_start_delay - 1

        for (i, byte) in enumerate(self.get_bytes(do_tokens=False)):

            # xCore should not be trying to send if we are trying to send..
            if xsi.sample_port_pins(usb_phy._txv) == 1:
                print("ERROR: Unexpected packet from xCORE (TxPacket 1)")

            wait(lambda x: usb_phy._clock.is_low())
            wait(lambda x: usb_phy._clock.is_high())
            wait(lambda x: usb_phy._clock.is_low())
            xsi.drive_periph_pin(usb_phy._rxdv, 1)
            xsi.drive_periph_pin(usb_phy._rxd, byte)

            if (self.rxe_assert_time != 0) and (self.rxe_assert_time == i):
                xsi.drive_periph_pin(usb_phy._rxer, 1)

            while rxv_count != 0:
                wait(lambda x: usb_phy._clock.is_high())
                wait(lambda x: usb_phy._clock.is_low())
                xsi.drive_periph_pin(usb_phy._rxdv, 0)
                rxv_count = rxv_count - 1

                # xCore should not be trying to send if we are trying to send..
                # We assume that the Phy internally blocks the TXValid signal to the Transmit State Machine
                # until the Rx packet has completed

                # if xsi.sample_port_pins(usb_phy._txv) == 1:
                #    print("ERROR: Unexpected packet from xCORE (TxPacket 2)")

            rxv_count = USB_DATA_VALID_COUNT[bus_speed]

        # Wait for last byte
        wait(lambda x: usb_phy._clock.is_high())
        wait(lambda x: usb_phy._clock.is_low())

        xsi.drive_periph_pin(usb_phy._rxdv, 0)
        xsi.drive_periph_pin(usb_phy._rxer, 0)

        rxa_end_delay = self.rxa_end_delay

        while rxa_end_delay != 0:
            # Wait for RXA fall delay TODO, this should be configurable
            wait(lambda x: usb_phy._clock.is_high())
            wait(lambda x: usb_phy._clock.is_low())
            rxa_end_delay = rxa_end_delay - 1

            # xCore should not be trying to send if we are trying to send..
            # We assume that the Phy internally blocks the TXValid signal to the Transmit State Machine
            # until the Rx packet has completed

            # if xsi.sample_port_pins(usb_phy._txv) == 1:
            #    print("ERROR: Unexpected packet from xCORE (TxPacket 3)")

        xsi.drive_periph_pin(usb_phy._rxa, 0)

    # Implemented such that we can generate malformed packets
    def get_bytes(self, do_tokens=False):
        bytes = []
        if do_tokens:
            bytes.append(self.pid)
        else:
            bytes.append(self.pid | ((~self.pid) << 4))
            for x in range(len(self.data_bytes)):
                bytes.append(self.data_bytes[x])
        return bytes


# DataPacket class, inherits from Usb Packet
class DataPacket(UsbPacket):
    def __init__(self, dataPayload=[], **kwargs):
        super(DataPacket, self).__init__(**kwargs)
        self.pid = kwargs.pop("pid", 0x3)  # DATA0
        self.data_bytes = dataPayload

    def get_packet_bytes(self):
        packet_bytes = []
        packet_bytes = self.data_bytes
        return packet_bytes

    def get_crc(self, packet_bytes):
        crc = GenCrc16(packet_bytes)
        return crc

    def get_bytes(self, do_tokens=False):

        bytes = []

        if do_tokens:
            bytes.append(self.pid)
        else:
            bytes.append(self.pid | (((~self.pid) & 0xF) << 4))

        packet_bytes = self.get_packet_bytes()
        for byte in packet_bytes:
            bytes.append(byte)

        if self.bad_crc == True:
            crc = 0xBEEF
        else:
            crc = self.get_crc(packet_bytes)

        # Append the 2 bytes of CRC onto the packet
        for i in range(0, 2):
            bytes.append((crc >> (8 * i)) & 0xFF)

        return bytes


class RxDataPacket(RxPacket, DataPacket):
    def __init__(self, **kwargs):
        _pid = self.pid = kwargs.pop("pid", 0x3)  # DATA0

        # Re-construct full PID - xCORE sends out full PIDn | PID on Tx
        super(RxDataPacket, self).__init__(
            pid=(_pid & 0xF) | (((~_pid) & 0xF) << 4), **kwargs
        )

    def __str__(self):
        return (
            super(DataPacket, self).__str__()
            + ": RX DataPacket: "
            + super(DataPacket, self).get_pid_str()
            + " "
            + str(self.data_bytes)
        )


class TxDataPacket(DataPacket, TxPacket):
    def __init__(self, **kwargs):
        super(TxDataPacket, self).__init__(**kwargs)

    def __str__(self):
        return (
            super(DataPacket, self).__str__()
            + ": TX DataPacket: "
            + super(DataPacket, self).get_pid_str()
            + " "
            + str(self.data_bytes)
            + " Valid CRC: "
            + str(not self.bad_crc)
            + "RXE Assert: "
            + str(self.rxe_assert_time)
        )


# Always TX
class TokenPacket(TxPacket):
    def __init__(self, **kwargs):
        super(TokenPacket, self).__init__(**kwargs)
        self.endpoint = kwargs.pop("endpoint", 0)
        self.valid = kwargs.pop("valid", 1)
        self.address = kwargs.pop("address", 0)

        # Generate correct crc5
        crc5 = GenCrc5(
            reflect(((self.endpoint & 0xF) << 7) | ((self.address & 0x7F) << 0), 11)
        )

        # Correct crc5 can be overridden
        self.crc5 = kwargs.pop("crc5", crc5)

        # TODO Always override data_valid count to match IFM for archs < XS3

    def get_bytes(self, do_tokens=False):
        bytes = []

        if do_tokens:
            bytes.append(self.pid & 0xF)
            bytes.append(self.endpoint)
        else:
            bytes.append(self.pid)

            tokenbyte0 = self.address | ((self.endpoint & 1) << 7)
            tokenbyte1 = (self.endpoint >> 1) | (self.crc5 << 3)

            bytes.append(tokenbyte0)
            bytes.append(tokenbyte1)

        return bytes

    def __str__(self):
        return (
            super(TokenPacket, self).__str__()
            + ": TokenPacket: "
            + super(TokenPacket, self).get_pid_str()
        )

    # Token valid
    def get_token_valid(self):
        return self.valid


class HandshakePacket(UsbPacket):
    def __init__(self, **kwargs):
        super(HandshakePacket, self).__init__(**kwargs)
        self.pid = kwargs.pop("pid", USB_PID["ACK"])  # Default to ACK

    def get_bytes(self, do_tokens=False):
        bytes = []
        bytes.append(self.pid)
        return bytes


class RxHandshakePacket(HandshakePacket, RxPacket):
    def __init__(self, **kwargs):
        super(RxHandshakePacket, self).__init__(**kwargs)
        self.pid = kwargs.pop(
            "pid", 0xD2
        )  # Default to ACK (not expect inverted bits on Rx)
        # self._timeout = kwargs.pop("timeout", RX_TX_DELAY)  # TODO handled by Super()

    def __str__(self):
        return (
            super(RxHandshakePacket, self).__str__()
            + ": RX HandshakePacket: "
            + super(RxHandshakePacket, self).get_pid_str()
        )


class TxHandshakePacket(HandshakePacket, TxPacket):
    def __init__(self, **kwargs):
        super(TxHandshakePacket, self).__init__(**kwargs)

    def get_bytes(self, do_tokens=False):
        bytes = []
        if do_tokens:
            bytes.append(self.pid)
        else:
            bytes.append(self.pid | ((~self.pid) << 4))
        return bytes

    def __str__(self):
        return (
            super(TxHandshakePacket, self).__str__()
            + ": TX HandshakePacket: "
            + super(TxHandshakePacket, self).get_pid_str()
        )
