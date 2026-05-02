// event-tracker.h
#ifndef METAVISION_SDK_CORE_EVENT_CLUSTER_TRACKER_H
#define METAVISION_SDK_CORE_EVENT_CLUSTER_TRACKER_H

#include <metavision/sdk/base/events/event_cd.h>
#include <vector>

namespace Metavision {

class EventClusterTracker {
public:
  inline EventClusterTracker(int width, int height,
                             Metavision::timestamp dt_threshold)
      : width_(width), height_(height), dt_threshold_(dt_threshold),
        last_event_time_(width * height, -1),
        pixel_cluster_id_(width * height, 0), next_cluster_id_(1) {
    cluster_parent_.push_back(0);
  }

  ~EventClusterTracker() = default;

  inline int get_pixel_cluster(int x, int y) {
    int id = pixel_cluster_id_[y * width_ + x];
    return (id == 0) ? 0 : find_cluster_root(id);
  }

  // Moved to public for direct access by the wrapper
  inline void process_single_event(const Metavision::EventCD &ev) {
    int x = ev.x;
    int y = ev.y;
    Metavision::timestamp t = ev.t;

    std::vector<int> active_neighbor_clusters;
    active_neighbor_clusters.reserve(8);

    for (int dy = -1; dy <= 1; ++dy) {
      for (int dx = -1; dx <= 1; ++dx) {
        if (dx == 0 && dy == 0)
          continue;

        int nx = x + dx;
        int ny = y + dy;

        if (nx >= 0 && nx < width_ && ny >= 0 && ny < height_) {
          int neighbor_idx = ny * width_ + nx;
          Metavision::timestamp neighbor_t = last_event_time_[neighbor_idx];

          if (neighbor_t != -1 && (t - neighbor_t) <= dt_threshold_) {
            int neighbor_cluster =
                find_cluster_root(pixel_cluster_id_[neighbor_idx]);
            active_neighbor_clusters.push_back(neighbor_cluster);
          }
        }
      }
    }

    int assigned_id = 0;

    if (active_neighbor_clusters.empty()) {
      assigned_id = next_cluster_id_++;
      cluster_parent_.push_back(assigned_id);
    } else if (active_neighbor_clusters.size() == 1) {
      assigned_id = active_neighbor_clusters[0];
    } else {
      assigned_id = active_neighbor_clusters[0];
      for (size_t i = 1; i < active_neighbor_clusters.size(); ++i) {
        int other_id = active_neighbor_clusters[i];
        if (other_id != assigned_id) {
          merge_clusters(assigned_id, other_id);
          assigned_id = find_cluster_root(assigned_id);
        }
      }
    }

    int current_idx = y * width_ + x;
    last_event_time_[current_idx] = t;
    pixel_cluster_id_[current_idx] = assigned_id;
  }

private:
  int width_;
  int height_;
  Metavision::timestamp dt_threshold_;
  std::vector<Metavision::timestamp> last_event_time_;
  std::vector<int> pixel_cluster_id_;
  int next_cluster_id_;
  std::vector<int> cluster_parent_;

  inline int find_cluster_root(int id) {
    int root = id;
    while (root != cluster_parent_[root]) {
      root = cluster_parent_[root];
    }
    int curr = id;
    while (curr != root) {
      int nxt = cluster_parent_[curr];
      cluster_parent_[curr] = root;
      curr = nxt;
    }
    return root;
  }

  inline void merge_clusters(int id1, int id2) {
    int root1 = find_cluster_root(id1);
    int root2 = find_cluster_root(id2);
    if (root1 != root2) {
      if (root1 < root2) {
        cluster_parent_[root2] = root1;
      } else {
        cluster_parent_[root1] = root2;
      }
    }
  }
};

} // namespace Metavision
#endif
