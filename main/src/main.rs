use hackrfone::{HackRfOne, iq_to_cplx_f32};
use num_complex::Complex;

fn main() {
    let mut hackrf = HackRfOne::new().expect("Failed to open HackRF").into_rx_mode().unwrap();
    hackrf.set_freq(434_000_000).unwrap();
    hackrf.set_sample_rate(2, 1).unwrap();

    loop{
        let data = HackRfOne::rx(&mut hackrf).unwrap();

        let samples: Vec<Complex<f32>> = data
        .chunks_exact(2)
        .map(|c| iq_to_cplx_f32(c[0] as u8, c[1] as u8))
        .collect();
        
        let mags: Vec<f32> = samples.iter().map(|s| s.norm()).collect();

        let threshold = 0.2;
        let bits: Vec<u8> = mags
            .iter()
            .map(|&m| if m > threshold { 1u8 } else { 0u8 })
            .collect();

        let mut bytes = Vec::new();
        for chunk in bits.chunks(8) {
            let mut byte = 0u8;
            for (i, &bit) in chunk.iter().enumerate() {
                byte |= bit << (7 - i);
            }
            bytes.push(byte);
        }

        println!("Received {} bytes", bytes.len());
        println!("{:02X?}", bytes);
    }
}
