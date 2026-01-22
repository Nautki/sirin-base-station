use hackrfone::{HackRfOne, RxMode, UnknownMode};
use std::time::{Duration, Instant};

fn main() -> Result<(), hackrfone::Error> {
    // 434 MHz (ISM / many telemetry links)
    const FC_HZ: u64 = 434_500_000;

    // HackRF sample rate must be in a supported range; 8 MS/s is a common choice.
    // The hackrfone crate uses (sample_rate_hz, divider) to program the clocking.
    const FS_HZ: u32 = 8_000_000;
    const DIV: u32 = 2;

    // Open first connected HackRF One
    let mut radio: HackRfOne<UnknownMode> =
        HackRfOne::new().expect("Failed to open HackRF One");

    // Basic configuration (keep it simple)
    radio.set_sample_rate(FS_HZ * DIV, DIV)?; //  [oai_citation:2‡Docs.rs](https://docs.rs/hackrfone/latest/hackrfone/struct.HackRfOne.html)
    radio.set_freq(FC_HZ)?;                   //  [oai_citation:3‡Docs.rs](https://docs.rs/hackrfone/latest/hackrfone/struct.HackRfOne.html)

    // Gains: start modest to avoid overload, then adjust
    radio.set_lna_gain(16)?; // 0..40-ish in steps (device dependent)
    radio.set_vga_gain(16)?; // 0..62-ish in steps (device dependent)

    // Optional: turn off front-end amp unless you really need it
    radio.set_amp_enable(false)?;

    // Switch into RX mode
    let mut radio: HackRfOne<RxMode> = radio.into_rx_mode()?;

    println!("Listening at {} Hz, {} sps ...", FC_HZ, FS_HZ);

    let mut last_print = Instant::now();

    loop {
        // Read a buffer of raw interleaved IQ bytes: [I0, Q0, I1, Q1, ...]
        let buf: Vec<u8> = radio.rx()?; //  [oai_citation:4‡Docs.rs](https://docs.rs/hackrfone/latest/hackrfone/struct.HackRfOne.html)

        // Compute average power (very rough "signal strength")
        // Interpret u8 bytes as i8 signed samples
        let mut sum_p: f64 = 0.0;
        let mut n: usize = 0;

        for iq in buf.chunks_exact(2) {
            let i = iq[0] as i8 as f64;
            let q = iq[1] as i8 as f64;
            sum_p += i * i + q * q;
            n += 1;
        }

        if last_print.elapsed() >= Duration::from_secs(1) && n > 0 {
            let mean_p = sum_p / (n as f64);

            // Convert to dBFS-ish (full-scale for signed 8-bit is about 127)
            let full_scale = 127.0_f64;
            let norm = mean_p / (2.0 * full_scale * full_scale);
            let dbfs = 10.0 * (norm.max(1e-12)).log10();

            println!("avg power: {:7.2} dBFS (rough)", dbfs);
            last_print = Instant::now();
        }
    }

    // (Unreachable in this minimal loop; you could add Ctrl-C handling and call stop_rx().)
    // radio.stop_rx()?;
    // Ok(())
}