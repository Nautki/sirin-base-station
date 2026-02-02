from gnuradio import gr
import sys
import signal
import numpy as np
import gnuradio.lora_sdr as lora_sdr
from gnuradio import soapy


class lora_RX(gr.top_block):
    def __init__(self):
        gr.top_block.__init__(self, "Lora Rx (HackRF via Soapy)", catch_exceptions=True)

        ##################################################
        # Variables
        ##################################################
        self.soft_decoding = soft_decoding = True

        # 128 chips per symbol => 2^SF = 128 => SF = 7
        self.sf = sf = 7

        # RF center frequency
        self.center_freq = center_freq = 434.5e6

        # LoRa BW (most common); if decode fails try 250000 or 500000
        self.bw = bw = 125000

        # HackRF-friendly sampling rate; keep (samp_rate / bw) integer
        self.samp_rate = samp_rate = 2_000_000  # 2e6 / 125e3 = 16

        # Coding rate 4/5 => cr = 1 (gr-lora_sdr convention)
        self.cr = cr = 1

        # Explicit header mode => impl_head = False
        self.impl_head = impl_head = False

        # CRC disabled
        self.has_crc = has_crc = False

        # Payload max (explicit header contains real length)
        self.pay_len = pay_len = 256

        # Sync word: 0x1E
        self.sync_word = sync_word = 0x1E

        ##################################################
        # Soapy HackRF Source
        ##################################################
        device = "driver=hackrf"
        dtype = "fc32"
        nchan = 1
        dev_args = ""       # e.g. "serial=..." if needed
        stream_args = ""
        tune_args = [""]    # one entry per channel
        other_settings = [""]

        self.soapy_source_0 = soapy.source(
            device, dtype, nchan,
            dev_args, stream_args,
            tune_args, other_settings
        )

        # Set sample rate / freq / bw after construction
        self.soapy_source_0.set_sample_rate(0, samp_rate)
        self.soapy_source_0.set_frequency(0, center_freq)
        self.soapy_source_0.set_bandwidth(0, bw)

        # Start with moderate gain; adjust if too quiet/clipping
        self.soapy_source_0.set_gain(0, 20)

        # Buffer sizing similar to UHD version
        self.soapy_source_0.set_min_output_buffer(int(np.ceil(samp_rate / bw * (2**sf + 2))))

        ##################################################
        # LoRa SDR blocks
        ##################################################
        self.lora_sdr_header_decoder_0 = lora_sdr.header_decoder(
            impl_head, cr, pay_len, has_crc,
            False,
            True   # verify explicit header checksum
        )

        self.lora_sdr_hamming_dec_0 = lora_sdr.hamming_dec(soft_decoding)
        self.lora_sdr_gray_mapping_0 = lora_sdr.gray_mapping(soft_decoding)

        self.lora_sdr_frame_sync_0 = lora_sdr.frame_sync(
            int(center_freq),
            bw,
            sf,
            impl_head,
            [sync_word],
            int(samp_rate / bw),
            8
        )

        self.lora_sdr_fft_demod_0 = lora_sdr.fft_demod(soft_decoding, True)
        self.lora_sdr_dewhitening_0 = lora_sdr.dewhitening()
        self.lora_sdr_deinterleaver_0 = lora_sdr.deinterleaver(soft_decoding)

        # CRC block can remain; since has_crc=False, CRC won't be required
        self.lora_sdr_crc_verif_0 = lora_sdr.crc_verif(1, False)

        ##################################################
        # Connections
        ##################################################
        self.msg_connect(
            (self.lora_sdr_header_decoder_0, 'frame_info'),
            (self.lora_sdr_frame_sync_0, 'frame_info')
        )

        self.connect((self.soapy_source_0, 0), (self.lora_sdr_frame_sync_0, 0))
        self.connect((self.lora_sdr_frame_sync_0, 0), (self.lora_sdr_fft_demod_0, 0))
        self.connect((self.lora_sdr_fft_demod_0, 0), (self.lora_sdr_gray_mapping_0, 0))
        self.connect((self.lora_sdr_gray_mapping_0, 0), (self.lora_sdr_deinterleaver_0, 0))
        self.connect((self.lora_sdr_deinterleaver_0, 0), (self.lora_sdr_hamming_dec_0, 0))
        self.connect((self.lora_sdr_hamming_dec_0, 0), (self.lora_sdr_header_decoder_0, 0))
        self.connect((self.lora_sdr_header_decoder_0, 0), (self.lora_sdr_dewhitening_0, 0))
        self.connect((self.lora_sdr_dewhitening_0, 0), (self.lora_sdr_crc_verif_0, 0))


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