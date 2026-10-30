
(* top *)
module lcd_top (
    (* iopad_external_pin, clkbuf_inhibit *) input pll_clk,

    (* iopad_external_pin *) output OSC_CTRL_EN,
    output PLL_REF_CLK_SELECTION,
    (* iopad_external_pin *) output PLL_CTRL_BYPASS,
    (* iopad_external_pin *) output PLL_CTRL_EN,
    (* iopad_external_pin *) output [5:0]  PLL_CTRL_REFDIV,
    (* iopad_external_pin *) output [11:0] PLL_CTRL_FBDIV,
    (* iopad_external_pin *) output [2:0]  PLL_CTRL_POSTDIV1,
    (* iopad_external_pin *) output [2:0]  PLL_CTRL_POSTDIV2,

    input i_rp_clk,
    input i_rp_strb,
    input i_rp_data_0,
    input i_rp_data_1,
    input i_rp_data_2,
    input i_rp_data_3,

    (* iopad_external_pin *) output reg o_lcd_sclk,
    (* iopad_external_pin *) output reg o_lcd_mosi,
    (* iopad_external_pin *) output reg o_lcd_dc,
    (* iopad_external_pin *) output reg o_lcd_cs,
    (* iopad_external_pin *) output reg o_lcd_rst,

    (* iopad_external_pin *) output o_lcd_sclk_oe,
    (* iopad_external_pin *) output o_lcd_mosi_oe,
    (* iopad_external_pin *) output o_lcd_dc_oe,
    (* iopad_external_pin *) output o_lcd_cs_oe,
    (* iopad_external_pin *) output o_lcd_rst_oe
);

    // ============================================================
    // 1. CLOCK CONFIGURATION
    // Target: 90 MHz from 50 MHz internal oscillator
    // ============================================================
	
    assign OSC_CTRL_EN           = 1'b1;
    assign PLL_CTRL_EN           = 1'b1;
    assign PLL_CTRL_BYPASS       = 1'b0;
    assign PLL_REF_CLK_SELECTION = 1'b0;

    assign PLL_CTRL_REFDIV       = 6'd1;
    assign PLL_CTRL_FBDIV        = 12'd27;
    assign PLL_CTRL_POSTDIV1     = 3'd5;
    assign PLL_CTRL_POSTDIV2     = 3'd3;

    // SPI SCLK = 90 MHz / (2 * 1) = 45 MHz.
    localparam [7:0] SPI_HALF_DIV = 8'd0;
    
	localparam [31:0] RESET_LOW_CYCLES  = 32'd900000;     // 10 ms
	localparam [31:0] RESET_HIGH_CYCLES = 32'd10800000;   // 120 ms
	localparam [31:0] SWRESET_CYCLES    = 32'd13500000;   // 150 ms
	localparam [31:0] SLEEP_OUT_CYCLES  = 32'd10800000;   // 120 ms
    assign o_lcd_sclk_oe = 1'b1;
    assign o_lcd_mosi_oe = 1'b1;
    assign o_lcd_dc_oe   = 1'b1;
    assign o_lcd_cs_oe   = 1'b1;
    assign o_lcd_rst_oe  = 1'b1;

    // ============================================================
    // 2. STATE MACHINE
    // ============================================================

    localparam [3:0]
        ST_RESET_LOW   = 4'd0,
        ST_RESET_WAIT  = 4'd1,
        ST_INIT_START  = 4'd2,
        ST_INIT_WAIT   = 4'd3,
        ST_DELAY       = 4'd4,
        ST_CASET_START = 4'd5,
        ST_CASET_WAIT  = 4'd6,
        ST_RASET_START = 4'd7,
        ST_RASET_WAIT  = 4'd8,
        ST_RAMWR_START = 4'd9,
        ST_RAMWR_WAIT  = 4'd10,
        ST_STREAM      = 4'd11;

    reg [3:0] state;
    reg [31:0] delay_count;
    reg [3:0] init_index;
    reg [3:0] cmd_substate;

    // ============================================================
    // 3. SPI TRANSMITTER
    // SPI mode preserved; divider corrected.
    // ============================================================

    reg [7:0] tx_data;
    reg [7:0] tx_shift;
    reg [3:0] tx_bits;
    reg [7:0] tx_divider;

    reg tx_start;
    reg tx_busy;
    reg tx_done;

    always @(posedge pll_clk) begin
        tx_done <= 1'b0;

        if (tx_start && !tx_busy) begin
            tx_shift   <= tx_data;
            tx_bits    <= 4'd8;
            tx_divider <= 8'd0;
            tx_busy    <= 1'b1;

            o_lcd_sclk <= 1'b0;
            o_lcd_mosi <= tx_data[7];
        end
        else if (tx_busy) begin
           if ((SPI_HALF_DIV == 0) ||
    			(tx_divider >= SPI_HALF_DIV)) begin
    				tx_divider <= 8'd0;


                if (!o_lcd_sclk) begin
                    o_lcd_sclk <= 1'b1;
                end
                else begin
                    o_lcd_sclk <= 1'b0;

                    tx_shift <= {tx_shift[6:0], 1'b0};
                    tx_bits  <= tx_bits - 1'b1;

                    if (tx_bits == 4'd1) begin
                        tx_busy <= 1'b0;
                        tx_done <= 1'b1;
                    end
                    else begin
                        o_lcd_mosi <= tx_shift[6];
                    end
                end
            end
            else begin
                tx_divider <= tx_divider + 1'b1;
            end
        end
        else begin
            o_lcd_sclk <= 1'b0;
        end
    end

    // ============================================================
    // 4. RP2040 INPUT SYNCHRONIZERS
    // ============================================================

    reg rp_clk_meta, rp_clk_sync, rp_clk_old;
    reg rp_strb_meta, rp_strb_sync;

    reg [3:0] data_meta;
    reg [3:0] data_sync;

    wire [3:0] rp_data = data_sync;
    wire rp_clk_rising = rp_clk_sync && !rp_clk_old;

    always @(posedge pll_clk) begin
        rp_clk_meta <= i_rp_clk;
        rp_clk_sync <= rp_clk_meta;
        rp_clk_old  <= rp_clk_sync;

        rp_strb_meta <= i_rp_strb;
        rp_strb_sync <= rp_strb_meta;

        data_meta <= {
            i_rp_data_3,
            i_rp_data_2,
            i_rp_data_1,
            i_rp_data_0
        };

        data_sync <= data_meta;
    end

    // ============================================================
    // 5. ASSEMBLE TWO NIBBLES INTO ONE BYTE
    // ============================================================

    reg rx_phase;
    reg [3:0] rx_high_nibble;
    reg [7:0] rx_byte;
    reg rx_valid;

    always @(posedge pll_clk) begin
        rx_valid <= 1'b0;

        if (!rp_strb_sync) begin
            rx_phase <= 1'b0;
        end
        else if (rp_clk_rising) begin
            if (!rx_phase) begin
                rx_high_nibble <= rp_data;
                rx_phase       <= 1'b1;
            end
            else begin
                rx_byte  <= {rx_high_nibble, rp_data};
                rx_valid <= 1'b1;
                rx_phase <= 1'b0;
            end
        end
    end

    // ============================================================
    // 6. FIFO AND FRAME TRACKING
    // 320 x 240 RGB565 = 153600 bytes per frame
    // ============================================================

    localparam [4:0] FIFO_DEPTH = 5'd16;

    reg [7:0] fifo_mem [0:15];
    reg [3:0] fifo_wr_ptr;
    reg [3:0] fifo_rd_ptr;
    reg [4:0] fifo_count;
    reg fifo_overflow;

    reg [17:0] frame_byte_count;

    wire frame_boundary =
        (state == ST_STREAM) &&
        tx_done &&
        (frame_byte_count == 18'd153599);

    wire fifo_pop =
        (state == ST_STREAM) &&
        !tx_busy &&
        !tx_start &&
        (fifo_count != 0);

    wire fifo_push =
        rx_valid &&
        (state == ST_STREAM) &&
        ((fifo_count < FIFO_DEPTH) || fifo_pop);

    always @(posedge pll_clk) begin
            if (fifo_push) begin
                fifo_mem[fifo_wr_ptr] <= rx_byte;
                fifo_wr_ptr <= fifo_wr_ptr + 1'b1;
            end

            if (fifo_pop)
                fifo_rd_ptr <= fifo_rd_ptr + 1'b1;

            case ({fifo_push, fifo_pop})
                2'b10: fifo_count <= fifo_count + 1'b1;
                2'b01: fifo_count <= fifo_count - 1'b1;
                default: fifo_count <= fifo_count;
            endcase

            if (rx_valid &&
                (state == ST_STREAM) &&
                (fifo_count == FIFO_DEPTH) &&
                !fifo_pop)
                fifo_overflow <= 1'b1;
        end

    // ============================================================
    // 7. LCD INITIALIZATION TABLE
    // ============================================================

    reg [7:0] init_byte;
    reg init_dc;

    always @(*) begin
        init_byte = 8'h00;
        init_dc   = 1'b0;

        case (init_index)
            0: begin init_byte = 8'h01; init_dc = 1'b0; end
            1: begin init_byte = 8'h11; init_dc = 1'b0; end
            2: begin init_byte = 8'h3A; init_dc = 1'b0; end
            3: begin init_byte = 8'h55; init_dc = 1'b1; end
            4: begin init_byte = 8'h36; init_dc = 1'b0; end
            5: begin init_byte = 8'h60; init_dc = 1'b1; end
            6: begin init_byte = 8'h20; init_dc = 1'b0; end
            7: begin init_byte = 8'h13; init_dc = 1'b0; end
            8: begin init_byte = 8'h29; init_dc = 1'b0; end
            default: begin init_byte = 8'h00; init_dc = 1'b0; end
        endcase
    end

    // ============================================================
    // 8. MAIN CONTROLLER
    // ============================================================

    always @(posedge pll_clk) begin
        tx_start <= 1'b0;

        case (state)

            // Hardware reset low for 10 ms at 100 MHz.
            ST_RESET_LOW: begin
                o_lcd_cs    <= 1'b1;
                o_lcd_rst   <= 1'b0;
                o_lcd_dc    <= 1'b0;
                delay_count <= 32'd0;
                init_index  <= 4'd0;

                if (delay_count >= RESET_LOW_CYCLES) begin
                    o_lcd_rst   <= 1'b1;
                    delay_count <= 32'd0;
                    state       <= ST_RESET_WAIT;
                end
                else begin
                    delay_count <= delay_count + 1'b1;
                end
            end

            // Wait 120 ms after releasing hardware reset.
            ST_RESET_WAIT: begin
                if (delay_count >= RESET_HIGH_CYCLES) begin
                    delay_count <= 32'd0;
                    init_index  <= 4'd0;
                    state       <= ST_INIT_START;
                end
                else begin
                    delay_count <= delay_count + 1'b1;
                end
            end

            ST_INIT_START: begin
                o_lcd_cs <= 1'b0;
                o_lcd_dc <= init_dc;
                tx_data  <= init_byte;
                tx_start <= 1'b1;
                state    <= ST_INIT_WAIT;
            end

            ST_INIT_WAIT: begin
                if (tx_done) begin
                    o_lcd_cs <= 1'b1;

                    if (init_index == 0 || init_index == 1) begin
                        delay_count <= 32'd0;
                        state       <= ST_DELAY;
                    end
                    else if (init_index == 8) begin
                        cmd_substate <= 4'd0;
                        state        <= ST_CASET_START;
                    end
                    else begin
                        init_index <= init_index + 1'b1;
                        state      <= ST_INIT_START;
                    end
                end
            end

            // Software reset and sleep-out delays.
            ST_DELAY: begin
                if ((init_index == 0 &&
                     delay_count >= SWRESET_CYCLES) ||
                    (init_index == 1 &&
                     delay_count >= SLEEP_OUT_CYCLES)) begin

                    delay_count <= 32'd0;
                    init_index  <= init_index + 1'b1;
                    state       <= ST_INIT_START;
                end
                else begin
                    delay_count <= delay_count + 1'b1;
                end
            end

            // CASET: columns 0..319.
            ST_CASET_START: begin
                o_lcd_cs <= 1'b0;
                o_lcd_dc <= (cmd_substate == 0) ? 1'b0 : 1'b1;

                case (cmd_substate)
                    0: tx_data <= 8'h2A;
                    1: tx_data <= 8'h00;
                    2: tx_data <= 8'h00;
                    3: tx_data <= 8'h01;
                    4: tx_data <= 8'h3F;
                    default: tx_data <= 8'h00;
                endcase

                tx_start <= 1'b1;
                state    <= ST_CASET_WAIT;
            end

            ST_CASET_WAIT: begin
                if (tx_done) begin
                    if (cmd_substate == 4) begin
                        o_lcd_cs     <= 1'b1;
                        cmd_substate <= 4'd0;
                        state        <= ST_RASET_START;
                    end
                    else begin
                        cmd_substate <= cmd_substate + 1'b1;
                        state        <= ST_CASET_START;
                    end
                end
            end

            // RASET: rows 8..247.
            ST_RASET_START: begin
                o_lcd_cs <= 1'b0;
                o_lcd_dc <= (cmd_substate == 0) ? 1'b0 : 1'b1;

                case (cmd_substate)
                    0: tx_data <= 8'h2B;
                    1: tx_data <= 8'h00;
                    2: tx_data <= 8'h00;
                    3: tx_data <= 8'h00;
                    4: tx_data <= 8'hEF;
                    default: tx_data <= 8'h00;
                endcase

                tx_start <= 1'b1;
                state    <= ST_RASET_WAIT;
            end

            ST_RASET_WAIT: begin
                if (tx_done) begin
                    if (cmd_substate == 4) begin
                        o_lcd_cs     <= 1'b1;
                        cmd_substate <= 4'd0;
                        state        <= ST_RAMWR_START;
                    end
                    else begin
                        cmd_substate <= cmd_substate + 1'b1;
                        state        <= ST_RASET_START;
                    end
                end
            end

            // Begin writing pixel data.
            ST_RAMWR_START: begin
                o_lcd_cs <= 1'b0;
                o_lcd_dc <= 1'b0;
                tx_data  <= 8'h2C;
                tx_start <= 1'b1;
                state    <= ST_RAMWR_WAIT;
            end

            ST_RAMWR_WAIT: begin
                if (tx_done) begin
                    o_lcd_cs         <= 1'b0;
                    o_lcd_dc         <= 1'b1;
                    frame_byte_count <= 18'd0;
                    state            <= ST_STREAM;
                end
            end

            // Pixel stream with frame counting.
            ST_STREAM: begin
    				if (tx_done) begin
        				if (frame_byte_count == 18'd153599)
            				frame_byte_count <= 18'd0;
        				else
            				frame_byte_count <= frame_byte_count + 1'b1;
    				end

    				if (fifo_pop) begin
        				tx_data  <= fifo_mem[fifo_rd_ptr];
        				tx_start <= 1'b1;
    				end
			end

            default: begin
                state <= ST_RESET_LOW;
            end
        endcase
    end

    // ============================================================
    // 9. POWER-UP INITIAL VALUES
    // ============================================================

    initial begin
        state        = ST_RESET_LOW;
        delay_count  = 32'd0;
        init_index   = 4'd0;
        cmd_substate = 4'd0;

        o_lcd_sclk   = 1'b0;
        o_lcd_mosi   = 1'b0;
        o_lcd_dc     = 1'b0;
        o_lcd_cs     = 1'b1;
        o_lcd_rst    = 1'b0;

        tx_data      = 8'd0;
        tx_shift     = 8'd0;
        tx_bits      = 4'd0;
        tx_divider   = 8'd0;
        tx_start     = 1'b0;
        tx_busy      = 1'b0;
        tx_done      = 1'b0;

        rp_clk_meta  = 1'b0;
        rp_clk_sync  = 1'b0;
        rp_clk_old   = 1'b0;
        rp_strb_meta = 1'b0;
        rp_strb_sync = 1'b0;
        data_meta    = 4'd0;
        data_sync    = 4'd0;

        rx_phase       = 1'b0;
        rx_high_nibble = 4'd0;
        rx_byte        = 8'd0;
        rx_valid       = 1'b0;

        fifo_wr_ptr   = 4'd0;
        fifo_rd_ptr   = 4'd0;
        fifo_count    = 5'd0;
        fifo_overflow = 1'b0;

        frame_byte_count = 18'd0;
    end

endmodule
