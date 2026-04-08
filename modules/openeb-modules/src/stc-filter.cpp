#include <iterator>
#include <metavision/sdk/base/events/event_cd.h>
#include <metavision/utils/pybind/sync_algorithm_process_helper.h>
#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <vector>

namespace py = pybind11;

namespace Metavision {

class SpatioTemporalContrastAlgorithm {
public:
  SpatioTemporalContrastAlgorithm(int width, int height, long long threshold,
                                  bool cut_trail = true, bool inverse = false)
      : width_(width), height_(height), threshold_(threshold),
        cut_trail_(cut_trail), inverse_(inverse) {
    states_.resize(width_ * height_);
  }

  void set_threshold(long long threshold) { threshold_ = threshold; }
  long long get_threshold() const { return threshold_; }

  void set_cut_trail(bool cut_trail) { cut_trail_ = cut_trail; }
  bool get_cut_trail() const { return cut_trail_; }

  void set_inverse(bool inverse) { inverse_ = inverse; }
  bool get_inverse() const { return inverse_; }

  template <typename InputIt, typename OutputIt>
  OutputIt process_events(InputIt it_begin, InputIt it_end, OutputIt inserter) {
    for (auto it = it_begin; it != it_end; ++it) {
      const auto &ev = *it;

      // Prevent out-of-bounds memory access for corrupted events
      if (ev.x >= width_ || ev.y >= height_) {
        continue;
      }

      const size_t idx = static_cast<size_t>(ev.y) * width_ + ev.x;
      auto &state = states_[idx];

      bool valid = false;

      // Check the spatio-temporal constraint (dt <= threshold)
      if (state.t_last >= 0) {
        long long dt = ev.t - state.t_last;
        if (dt <= threshold_) {
          valid = true;
        }
      }

      // Process strong trail removal
      if (cut_trail_) {
        // Reset trail status on polarity change
        if (state.last_pol != -1 && state.last_pol != ev.p) {
          state.is_in_trail = false;
        }

        if (valid) {
          if (state.is_in_trail) {
            valid = false; // Block event, currently cutting trail
          } else {
            state.is_in_trail = true; // First strong STC event, initiate trail
                                      // cutting for subsequent events
          }
        }
        state.last_pol = ev.p;
      }

      state.t_last = ev.t;

      // Output the event if it matches the desired state (standard or inverse)
      if (valid != inverse_) {
        *inserter++ = ev;
      }
    }
    return inserter;
  }

private:
  struct PixelState {
    long long t_last = -1;
    int16_t last_pol = -1;
    bool is_in_trail = false;
  };

  int width_, height_;
  long long threshold_;
  bool cut_trail_;
  bool inverse_;
  std::vector<PixelState> states_;
};

} // namespace Metavision

// Pybind11 Module Definition
PYBIND11_MODULE(stc_filter, m) {
  m.doc() = "Spatio-Temporal Contrast Filter for Event-based data";

  py::class_<Metavision::SpatioTemporalContrastAlgorithm>(
      m, "SpatioTemporalContrastAlgorithm")
      .def(py::init<int, int, long long, bool, bool>(), py::arg("width"),
           py::arg("height"), py::arg("threshold"), py::arg("cut_trail") = true,
           py::arg("inverse") = false)
      .def_static("get_empty_output_buffer",
                  &Metavision::getEmptyPODBuffer<Metavision::EventCD>,
                  Metavision::doc_get_empty_output_buffer_str)
      .def_property("threshold",
                    &Metavision::SpatioTemporalContrastAlgorithm::get_threshold,
                    &Metavision::SpatioTemporalContrastAlgorithm::set_threshold)
      .def_property("cut_trail",
                    &Metavision::SpatioTemporalContrastAlgorithm::get_cut_trail,
                    &Metavision::SpatioTemporalContrastAlgorithm::set_cut_trail)
      .def_property("inverse",
                    &Metavision::SpatioTemporalContrastAlgorithm::get_inverse,
                    &Metavision::SpatioTemporalContrastAlgorithm::set_inverse)
      .def(
          "process_events",
          &Metavision::process_events_array_sync<
              Metavision::SpatioTemporalContrastAlgorithm, Metavision::EventCD>,
          py::arg("input_np"), py::arg("output_buf"),
          Metavision::doc_process_events_array_sync_str)
      .def(
          "process_events",
          &Metavision::process_events_buffer_sync<
              Metavision::SpatioTemporalContrastAlgorithm, Metavision::EventCD>,
          py::arg("input_buf"), py::arg("output_buf"),
          Metavision::doc_process_events_buffer_sync_str)
      .def(
          "process_events_",
          &Metavision::process_events_array_sync_inplace<
              Metavision::SpatioTemporalContrastAlgorithm, Metavision::EventCD>,
          py::arg("events_np"),
          Metavision::doc_process_events_array_sync_inplace_str);
}
