#include <cstdint>
#include <memory>
#include <stdexcept>
#include <string>

#include <metavision/hal/device/device.h>
#include <metavision/hal/device/device_discovery.h>
#include <metavision/hal/facilities/i_events_stream.h>
#include <metavision/hal/facilities/i_events_stream_decoder.h>
#include <metavision/hal/utils/raw_file_config.h>
#include <metavision/sdk/base/utils/error_utils.h>
#include <metavision/sdk/base/utils/log.h>

#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace py = pybind11;

namespace metavision {

class RawCutter {
public:
  RawCutter() : n_events_to_read_(1024), output_file_path_("") {}
  ~RawCutter() = default;

  // Configuration Methods
  void set_events_to_read(uint32_t n_events) { n_events_to_read_ = n_events; }

  void set_output_file_path(const std::string &path) {
    output_file_path_ = path;
  }

  // Main Execution Method
  bool cut_file(const std::string &file, int64_t start_us, int64_t end_us) {
    if (end_us <= start_us) {
      throw std::invalid_argument("end_us must be strictly less than start_us");
      return false;
    }

    std::string out_file = output_file_path_;

    // Auto-generate output file name if not explicitly configured
    if (out_file.empty()) {
      size_t dot_pos = file.find_last_of('.');
      std::string base_name =
          (dot_pos == std::string::npos) ? file : file.substr(0, dot_pos);
      out_file = base_name + "_cut_" + std::to_string(start_us) + "_" +
                 std::to_string(end_us) + ".raw";
    }

    Metavision::timestamp start_ts =
        static_cast<Metavision::timestamp>(start_us);
    Metavision::timestamp end_ts = static_cast<Metavision::timestamp>(end_us);

    std::unique_ptr<Metavision::Device> device;
    Metavision::RawFileConfig file_config;
    file_config.n_events_to_read_ = n_events_to_read_;

    device = Metavision::DeviceDiscovery::open_raw_file(file, file_config);

    Metavision::I_EventsStreamDecoder *i_eventsstreamdecoder =
        device->get_facility<Metavision::I_EventsStreamDecoder>();
    Metavision::I_EventsStream *i_eventsstream =
        device->get_facility<Metavision::I_EventsStream>();

    if (!i_eventsstreamdecoder || !i_eventsstream) {
      throw std::domain_error("device does not support event streaming.");
      return false;
    }

    i_eventsstream->start();

    bool recording = false;
    Metavision::timestamp last_ts = 0;

    while (true) {
      if (!recording) {
        if (last_ts >= start_ts) {
          i_eventsstream->log_raw_data(out_file);
          recording = true;
        }
      } else {
        if (last_ts >= end_ts) {
          i_eventsstream->stop_log_raw_data();
          break;
        }
      }

      if (i_eventsstream->wait_next_buffer() < 0) {
        // No more events available (end of file reached)
        break;
      }

      // Retrieve raw buffer
      auto ev_buffer = i_eventsstream->get_latest_raw_data();

      // Decode the raw buffer
      i_eventsstreamdecoder->decode(ev_buffer);

      // Update last timestamp
      last_ts = i_eventsstreamdecoder->get_last_timestamp();
    }

    if (!recording) {
      "after the end of the input file";
      throw std::domain_error(
          "The last timestamp of the file that fits within the provided range, "
          "must be less than the provided start timestamp.");
    }

    return true;
  }

private:
  uint32_t n_events_to_read_;
  std::string output_file_path_;
};
} // namespace metavision

PYBIND11_MODULE(raw_cutter_py, m) {
  m.doc() = "Python bindings for the Metavision RawCutter class";

  py::class_<metavision::RawCutter>(m, "RawCutter")
      .def(py::init<>())
      .def("set_events_to_read", &metavision::RawCutter::set_events_to_read,
           py::arg("n_events"), "Set the number of events to read per buffer.")
      .def("set_output_file_path", &metavision::RawCutter::set_output_file_path,
           py::arg("path"), "Explicitly set the output raw file path.")
      .def("cut_file", &metavision::RawCutter::cut_file, py::arg("file"),
           py::arg("start_us"), py::arg("end_us"),
           "Cut the raw file between start_us and end_us (in microseconds).");
}
