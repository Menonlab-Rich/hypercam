//! Pendulum Drop and Camera Trigger
//!
//! This firmware controls an electromagnet to drop a pendulum and uses a
//! photo-gate to trigger an event camera via an opto-isolator.
//!
//! Wiring:
//! - EM_RELEASE (Output to MOSFET) => GPIO1
//! - PHOTO_GATE (Input)            => GPIO2
//! - RELEASE_BUTTON (Input)        => GPIO3
//! - CAMERA_TRIGGER (Output)       => GPIO7

#![no_std]
#![no_main]

use core::cell::RefCell;

use critical_section::Mutex;
use esp_backtrace as _;
use esp_hal::{
    gpio::{Event, Input, InputConfig, Io, Level, Output, OutputConfig, Pull},
    handler, main, peripherals, ram,
    xtensa_lx::timer::delay,
};

esp_bootloader_esp_idf::esp_app_desc!();

static PHOTO_GATE: Mutex<RefCell<Option<Input>>> = Mutex::new(RefCell::new(None));
static CAMERA_TRIGGER: Mutex<RefCell<Option<Output>>> = Mutex::new(RefCell::new(None));

#[main]
fn main() -> ! {
    esp_println::logger::init_logger_from_env();
    let peripherals = esp_hal::init(esp_hal::Config::default());

    let mut io = Io::new(peripherals.IO_MUX);
    io.set_interrupt_handler(handler);

    // EM release drives the gate to the mosfet that controls the EM that holds the pendulum
    let mut em_release = Output::new(peripherals.GPIO1, Level::High, OutputConfig::default());

    // The release button will trigger the em_release to go low
    let release_button = Input::new(
        peripherals.GPIO3,
        InputConfig::default().with_pull(Pull::Up),
    );

    // photo_gate is the configured peripheral
    let config_in = InputConfig::default().with_pull(Pull::Up);
    let mut photo_gate = Input::new(peripherals.GPIO2, config_in);

    // camera trigger connects to the anode of an opto-isolator to trigger the event camera
    let config_out = OutputConfig::default().with_pull(Pull::Up);
    let camera_trigger = Output::new(peripherals.GPIO7, Level::Low, config_out);

    critical_section::with(|cs| {
        // setup globals correctly
        photo_gate.listen(Event::FallingEdge);
        PHOTO_GATE.borrow_ref_mut(cs).replace(photo_gate);
        CAMERA_TRIGGER.borrow_ref_mut(cs).replace(camera_trigger);
    });

    loop {
        // Mirror the release button state to the EM release pin.
        // When the button is pressed (pulled low), the EM loses power and the pendulum drops.
        if release_button.is_low() {
            em_release.set_low();
        } else {
            em_release.set_high();
        }
    }
}

#[handler]
#[ram]
fn handler() {
    critical_section::with(|cs| {
        let mut gate_ref = PHOTO_GATE.borrow_ref_mut(cs);

        // Safely check if the photo gate triggered the interrupt
        if let Some(gate) = gate_ref.as_mut() {
            if gate.is_interrupt_set() {
                let mut trigger_ref = CAMERA_TRIGGER.borrow_ref_mut(cs);
                if let Some(trigger) = trigger_ref.as_mut() {
                    // Pulse the opto-isolator
                    trigger.set_high();

                    // Delay for enough cycles to trigger the opto-isolator.
                    // Assuming a 160MHz clock, 8000 cycles is ~50 microseconds.
                    delay(8000);

                    // Reset the trigger so subsequent interrupts can fire
                    trigger.set_low();
                }

                // Clear the interrupt flag
                gate.clear_interrupt();
            }
        }
    });
}
