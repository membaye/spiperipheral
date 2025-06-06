# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from cocotb.triggers import ClockCycles
from cocotb.types import Logic
from cocotb.types import LogicArray

async def await_half_sclk(dut):
    """Wait for the SCLK signal to go high or low."""
    start_time = cocotb.utils.get_sim_time(units="ns")
    while True:
        await ClockCycles(dut.clk, 1)
        # Wait for half of the SCLK period (10 us)
        if (start_time + 100*100*0.5) < cocotb.utils.get_sim_time(units="ns"):
            break
    return

def ui_in_logicarray(ncs, bit, sclk):
    """Setup the ui_in value as a LogicArray."""
    return LogicArray(f"00000{ncs}{bit}{sclk}")

async def send_spi_transaction(dut, r_w, address, data):
    """
    Send an SPI transaction with format:
    - 1 bit for Read/Write
    - 7 bits for address
    - 8 bits for data
    
    Parameters:
    - r_w: boolean, True for write, False for read
    - address: int, 7-bit address (0-127)
    - data: LogicArray or int, 8-bit data
    """
    # Convert data to int if it's a LogicArray
    if isinstance(data, LogicArray):
        data_int = int(data)
    else:
        data_int = data
    # Validate inputs
    if address < 0 or address > 127:
        raise ValueError("Address must be 7-bit (0-127)")
    if data_int < 0 or data_int > 255:
        raise ValueError("Data must be 8-bit (0-255)")
    # Combine RW and address into first byte
    first_byte = (int(r_w) << 7) | address
    # Start transaction - pull CS low
    sclk = 0
    ncs = 0
    bit = 0
    # Set initial state with CS low
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    await ClockCycles(dut.clk, 1)
    # Send first byte (RW + Address)
    for i in range(8):
        bit = (first_byte >> (7-i)) & 0x1
        # SCLK low, set COPI
        sclk = 0
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
        # SCLK high, keep COPI
        sclk = 1
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
    # Send second byte (Data)
    for i in range(8):
        bit = (data_int >> (7-i)) & 0x1
        # SCLK low, set COPI
        sclk = 0
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
        # SCLK high, keep COPI
        sclk = 1
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
    # End transaction - return CS high
    sclk = 0
    ncs = 1
    bit = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    await ClockCycles(dut.clk, 600)
    return ui_in_logicarray(ncs, bit, sclk)

@cocotb.test()
async def test_spi(dut):
    dut._log.info("Start SPI test")

    # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    dut._log.info("Test project behavior")
    dut._log.info("Write transaction, address 0x00, data 0xF0")
    ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0xF0)  # Write transaction
    assert dut.uo_out.value == 0xF0, f"Expected 0xF0, got {dut.uo_out.value}"
    await ClockCycles(dut.clk, 1000) 

    dut._log.info("Write transaction, address 0x01, data 0xCC")
    ui_in_val = await send_spi_transaction(dut, 1, 0x01, 0xCC)  # Write transaction
    assert dut.uio_out.value == 0xCC, f"Expected 0xCC, got {dut.uio_out.value}"
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x30 (invalid), data 0xAA")
    ui_in_val = await send_spi_transaction(dut, 1, 0x30, 0xAA)
    await ClockCycles(dut.clk, 100)

    dut._log.info("Read transaction (invalid), address 0x00, data 0xBE")
    ui_in_val = await send_spi_transaction(dut, 0, 0x30, 0xBE)
    assert dut.uo_out.value == 0xF0, f"Expected 0xF0, got {dut.uo_out.value}"
    await ClockCycles(dut.clk, 100)
    
    dut._log.info("Read transaction (invalid), address 0x41 (invalid), data 0xEF")
    ui_in_val = await send_spi_transaction(dut, 0, 0x41, 0xEF)
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x02, data 0xFF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0xFF)  # Write transaction
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x04, data 0xCF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xCF)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0xFF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xFF)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0x00")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x00)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0x01")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x01)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("SPI test completed successfully")

@cocotb.test()
async def test_pwm_freq(dut):
    # need to measure freq of PWM signal produced on uo_out after sending spi control commands

    dut._log.info("Start PWM frequency test")

    # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    await send_spi_transaction(dut, 1, 0x04, 0x80) # set duty cycle to 50%
    await send_spi_transaction(dut, 1, 0x00, 0x01) # enable output
    await send_spi_transaction(dut, 1, 0x02, 0x01) # enabl pwm

    await ClockCycles(dut.clk, 5)

    begin = cocotb.utils.get_sim_time(units="ns") # time start sampled at rise
    to = 1e6
    
    while dut.uo_out.value != 0: # keep going until next fall
        await ClockCycles(dut.clk, 1)
        if (cocotb.utils.get_sim_time(units="ns") - begin > to):
            return -1

    while dut.uo_out.value == 0: # keep going until next rise
        await ClockCycles(dut.clk, 1)
        if (cocotb.utils.get_sim_time(units="ns") - begin > to):
            return -1
        
    timestart = cocotb.utils.get_sim_time(units="ns")

    while dut.uo_out.value != 0: # keep going until next fall
        await ClockCycles(dut.clk, 1)

    while dut.uo_out.value == 0: # keep going until next rise
        await ClockCycles(dut.clk, 1)
 
    frequency = 1/((cocotb.utils.get_sim_time(units="ns") - timestart) * (1e-9)) # unit conversion

    dut._log.info(f'Frequency: {frequency}')

    assert frequency >= 2970 and frequency <= 3030, "Frequency is out of bounds!"

    dut._log.info("PWM Frequency test completed successfully")


@cocotb.test()
async def test_pwm_duty(dut):
    # identical to freq test, need to first find period [(cocotb.utils.get_sim_time(units="ns") - timestart) * (1e-9)]
    # then, we test pwm duty cycle at 0%, 50%, and 100% by ensuring when configured to 50%, it actually is;
    # and for 0% and 100%, we check for no rising edges and no falling edges respectively.

    dut._log.info("Start PWM duty cycle test")

    # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    await send_spi_transaction(dut, 1, 0x04, 0x80) # set duty cycle to 50%
    await send_spi_transaction(dut, 1, 0x00, 0x01) # enable output
    await send_spi_transaction(dut, 1, 0x02, 0x01) # enabl pwm

    await ClockCycles(dut.clk, 5)

    begin = cocotb.utils.get_sim_time(units="ns") # time start sampled at rise
    to = 1e6
    
    while dut.uo_out.value != 0: # keep going until next fall
        await ClockCycles(dut.clk, 1)
        if (cocotb.utils.get_sim_time(units="ns") - begin > to):
            return -1

    while dut.uo_out.value == 0: # keep going until next rise
        await ClockCycles(dut.clk, 1)
        if (cocotb.utils.get_sim_time(units="ns") - begin > to):
            return -1
        
    timestart = cocotb.utils.get_sim_time(units="ns")

    while dut.uo_out.value != 0: # keep going until next fall
        await ClockCycles(dut.clk, 1)

    while dut.uo_out.value == 0: # keep going until next rise
        await ClockCycles(dut.clk, 1)

    period = cocotb.utils.get_sim_time(units="ns") - timestart

    # 50% test
    begin = cocotb.utils.get_sim_time(units="ns") # time start sampled at rise
    to = 1e6

    while dut.uo_out.value != 0: # keep going until next fall
        await ClockCycles(dut.clk, 1)
        if (cocotb.utils.get_sim_time(units="ns") - begin > to):
            return -1

    while dut.uo_out.value == 0: # keep going until next rise
        await ClockCycles(dut.clk, 1)
        if (cocotb.utils.get_sim_time(units="ns") - begin > to):
            return -1

    timestart = cocotb.utils.get_sim_time(units="ns")

    while dut.uo_out.value != 0: # keep going until next fall
        await ClockCycles(dut.clk, 1)

    highperiod = cocotb.utils.get_sim_time(units="ns") - timestart # need to know high time

    dutycycle = (highperiod/period) * (100)

    dut._log.info(f'At expected 50% duty cycle, recorded value is: {dutycycle}%')
    assert dutycycle == 50, "Duty cycle is expected to be 50%!"

    # 0% test
    await send_spi_transaction(dut, 1, 0x04, 0x00) # set duty cycle to 0%
    begin = cocotb.utils.get_sim_time(units="ns")
    to = 1e4

    while dut.uo_out.value == 0: # ensuring there are no rising edges on 0%
        await ClockCycles(dut.clk, 1)
        if (dut.uo_out.value != 0):
            assert dut.uo_out.value == 0, "At 0% duty cycle, signal should never go high!"
        if (cocotb.utils.get_sim_time(units="ns") - begin > to):
            break

    dut._log.info("Duty Cycle 0%: PASS")

    # 100% test
    await send_spi_transaction(dut, 1, 0x04, 0xFF) # set duty cycle to 100%
    begin = cocotb.utils.get_sim_time(units="ns")
    to = 1e4

    while dut.uo_out.value != 0: # ensuring there no falling edges on 100%
        await ClockCycles(dut.clk, 1)
        if (dut.uo_out.value == 0):
            assert dut.uo_out.value != 0, "At 100% duty cycle, signal should never go low!"
        if (cocotb.utils.get_sim_time(units="ns") - begin > to):
            break
    dut._log.info("Duty Cycle 100%: PASS")

    dut._log.info("PWM Duty Cycle test completed successfully")