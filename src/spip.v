/*
 * Copyright (c) 2025 Matthew Embaye
 * SPDX-License-Identifier: Apache-2.0
 */

/* system will do 4 main things:
1. sync the signal
2. shift one bit per rising edge of clk
   '--> when cs goes low, 16 bits are shifted. (0 is read/write, 1-6 is address, and 7-15 is the data)
3. detect when bits are recieved and do latch command
4. decode to write to pwm registers
*/

`default_nettype none

module spip(

input wire clk,
input wire rst_n,

input wire spi_sclk,
input wire spi_copi,
input wire spi_cs,

output reg [7:0] en_reg_out_15_8,
output reg [7:0] en_reg_out_7_0,
output reg [7:0] en_reg_pwm_15_8,
output reg [7:0] en_reg_pwm_7_0,
output reg [7:0] pwm_duty_cycle

);

reg sclk_sync_0, sclk_sync_1;
reg cs_sync_0, cs_sync_1;
reg copi_sync_0, copi_sync_1;

always @ (posedge clk or negedge rst_n) begin // syncing
    if (!rst_n) begin
        sclk_sync_0 <= 1'b0;
        sclk_sync_1 <= 1'b0;

        cs_sync_0   <= 1'b1; // active low
        cs_sync_1   <= 1'b1;

        copi_sync_0 <= 1'b0;
        copi_sync_1 <= 1'b0;
    end else begin
        sclk_sync_0 <= spi_sclk;
        sclk_sync_1 <= sclk_sync_0;

        cs_sync_0   <= spi_cs;
        cs_sync_1   <= cs_sync_0;

        copi_sync_0 <= spi_copi;
        copi_sync_1 <= copi_sync_0;
    end
end

// now i need to detect the rising and falling edges; so that it may start transaction on fall, shift on rise

wire sclk_rise = sclk_sync_0 & ~(sclk_sync_1);
wire sclk_fall = ~(sclk_sync_0) & sclk_sync_1;

wire scs_rise = cs_sync_0 & ~(cs_sync_1);
wire scs_fall = ~(cs_sync_0) & cs_sync_1;

// shift register

reg [15:0] shift_reg;
reg [3:0] bit_count;
reg trans_compl;

always @ (posedge clk or negedge rst_n) begin
    if(!rst_n) begin // reset case
        shift_reg <= 16'b0;
        bit_count <= 4'b0;
        trans_compl <= 1'b0;
    end else begin
        trans_compl <= 1'b0;

        if (!cs_sync_1) begin // no shift can happen unless cs is low
            if(sclk_rise) begin
                shift_reg <= {shift_reg[14:0], copi_sync_1}; // shift in one bit from copi on each rising edge
                bit_count <= bit_count + 1;

                if(bit_count == 4'b1111) begin // when 16 bits are completed, complete transaction
                    trans_compl <= 1'b1;
                end
            end
        end else begin
            bit_count <= 4'b0; // reset if cs goes high
        end
    end
end

// now decode and write. as stated prev, 0 is read/write, 1-6 is address, and 7-15 is the data

wire read_write = shift_reg[15];
wire [6:0]address = shift_reg[14:8];
wire [7:0]data = shift_reg[7:0];

always @ (posedge clk or negedge rst_n) begin
 if (!rst_n) begin // reset case
        en_reg_out_15_8 <= 8'b0;
        en_reg_out_7_0  <= 8'b0;
        en_reg_pwm_15_8 <= 8'b0;
        en_reg_pwm_7_0  <= 8'b0;
        pwm_duty_cycle  <= 8'b0;
    end else begin
        if (trans_compl && read_write) begin // latch data
            case (address)
                7'b0000000: en_reg_out_7_0  <= data;
                7'b0000001: en_reg_out_15_8 <= data;
                7'b0000010: en_reg_pwm_7_0  <= data;
                7'b0000011: en_reg_pwm_15_8 <= data;
                7'b0000100: pwm_duty_cycle  <= data;
                default: ; // do nothing for unrecognized addresses
            endcase
        end
    end
end
endmodule