from gnuradio import gr
from gnuradio import blocks
import sys
import signal
import numpy as np
import gnuradio.lora_sdr as lora_sdr
from gnuradio import soapy
import base64
import pmt

class lora_RX(gr.top_block):
    def __init__(self):
        gr.top_block.__init__(self, "Lora Rx (HackRF via Soapy)", catch_exceptions=True)

        ##################################################
        # Variables
        ##################################################
        self.soft_decoding = soft_decoding = True
        self.sf = sf = 7
        self.center_freq = center_freq = 434.5e6
        self.bw = bw = 125_000
        self.samp_rate = samp_rate = 2_000_000
        self.cr = cr = 1
        self.impl_head = impl_head = False
        self.has_crc = has_crc = False
        self.pay_len = pay_len = 256
        self.sync_word = sync_word = 0x12

        ##################################################
        # Soapy HackRF Source
        ##################################################
        device = "driver=hackrf"
        dtype = "fc32"
        nchan = 1
        dev_args = ""
        stream_args = ""
        tune_args = [""]
        other_settings = [""]
        
        self.soapy_source_0 = soapy.source(device, dtype, nchan, dev_args, stream_args, tune_args, other_settings)
        self.soapy_source_0.set_sample_rate(0, samp_rate)
        self.soapy_source_0.set_frequency(0, center_freq)
        self.soapy_source_0.set_bandwidth(0, bw)
        self.soapy_source_0.set_gain(0, 20)
        self.soapy_source_0.set_min_output_buffer(int(np.ceil(samp_rate / bw * (2**sf + 2))))

        ##################################################
        # LoRa SDR blocks
        ##################################################
        self.lora_sdr_header_decoder_0 = lora_sdr.header_decoder(impl_head, cr, pay_len, has_crc, False, True)
        self.lora_sdr_hamming_dec_0 = lora_sdr.hamming_dec(soft_decoding)
        self.lora_sdr_gray_mapping_0 = lora_sdr.gray_mapping(soft_decoding)
        self.lora_sdr_frame_sync_0 = lora_sdr.frame_sync(int(center_freq), bw, sf, impl_head, [sync_word], int(samp_rate / bw), 8)
        self.lora_sdr_fft_demod_0 = lora_sdr.fft_demod(soft_decoding, True)
        self.lora_sdr_dewhitening_0 = lora_sdr.dewhitening()
        self.lora_sdr_deinterleaver_0 = lora_sdr.deinterleaver(soft_decoding)
        self.lora_sdr_crc_verif_0 = lora_sdr.crc_verif(1, False)
        
        # Added to print packets to terminal
        self.blocks_message_debug_0 = blocks.message_debug()

        ##################################################
        # Connections
        ##################################################
        self.msg_connect((self.lora_sdr_header_decoder_0, 'frame_info'), (self.lora_sdr_frame_sync_0, 'frame_info'))
        
        # Packet Printing Connection
        self.msg_connect((self.lora_sdr_crc_verif_0, 'msg'), (self.blocks_message_debug_0, 'print'))

        self.connect((self.soapy_source_0, 0), (self.lora_sdr_frame_sync_0, 0))
        self.connect((self.lora_sdr_frame_sync_0, 0), (self.lora_sdr_fft_demod_0, 0))
        self.connect((self.lora_sdr_fft_demod_0, 0), (self.lora_sdr_gray_mapping_0, 0))
        self.connect((self.lora_sdr_gray_mapping_0, 0), (self.lora_sdr_deinterleaver_0, 0))
        self.connect((self.lora_sdr_deinterleaver_0, 0), (self.lora_sdr_hamming_dec_0, 0))
        self.connect((self.lora_sdr_hamming_dec_0, 0), (self.lora_sdr_header_decoder_0, 0))
        self.connect((self.lora_sdr_header_decoder_0, 0), (self.lora_sdr_dewhitening_0, 0))
        self.connect((self.lora_sdr_dewhitening_0, 0), (self.lora_sdr_crc_verif_0, 0))

class PrintBase64(gr.basic_block):
    def __init__(self):
        gr.basic_block.__init__(self,
            name="PrintBase64",
            in_sig=None,
            out_sig=None)
        # Register an input message port named 'in'
        self.message_port_register_in(pmt.intern('in'))
        self.set_msg_handler(pmt.intern('in'), self.handle_msg)

    def handle_msg(self, msg):
        try:
            # PDU is a pair: (metadata_dict, data_vector)
            # pmt.cdr(msg) gets the data_vector part
            payload = pmt.cdr(msg)
            
            # Convert the PDU u8vector to a standard Python byte array
            data_bytes = bytes(pmt.u8vector_elements(payload))
            
            # Encode to Base64
            b64_str = base64.b64encode(data_bytes).decode('utf-8')
            
            print(f"Base64 Message: {b64_str}")
        except Exception as e:
            print(f"Error decoding message: {e}")



def main():
    tb = lora_RX()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    tb.start()
    try:
        input("Press Enter to quit: ")
    except EOFError:
        pass
    tb.stop()
    tb.wait()

if __name__ == "__main__":
    main()
