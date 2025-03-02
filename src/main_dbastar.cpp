#include <fstream>
#include <iostream>
#include <algorithm>
#include <chrono>

#include <yaml-cpp/yaml.h>
#include <msgpack.hpp>

// #include <boost/functional/hash.hpp>
#include <boost/program_options.hpp>
#include <boost/heap/d_ary_heap.hpp>

// OMPL headers
#include <ompl/base/spaces/RealVectorStateSpace.h>
#include <ompl/control/SpaceInformation.h>
#include <ompl/control/spaces/RealVectorControlSpace.h>

#include <ompl/datastructures/NearestNeighbors.h>
#include <ompl/datastructures/NearestNeighborsSqrtApprox.h>
#include <ompl/datastructures/NearestNeighborsGNATNoThreadSafety.h>

#include "robots.h"
#include "robotStatePropagator.hpp"
#include "fclStateValidityChecker.hpp"
#include "fclHelper.hpp"

namespace ob = ompl::base;
namespace oc = ompl::control;

ob::State* allocAndFillState(std::shared_ptr<ompl::control::SpaceInformation> si, const YAML::Node& node)
{
  ob::State* state = si->allocState();
  std::vector<double> reals;
  for (const auto &value : node) {
    reals.push_back(value.as<double>());
  }
  si->getStateSpace()->copyFromReals(state, reals);
  return state;
}

std::ofstream& printState(std::ofstream &stream, std::shared_ptr<ompl::control::SpaceInformation> si, const ob::State* state)
{
  std::vector<double> reals;
  si->getStateSpace()->copyToReals(reals, state);
  stream << "[";
  for (size_t d = 0; d < reals.size(); ++d)
  {
    stream << reals[d];
    if (d < reals.size() - 1)
    {
      stream << ",";
    }
  }
  stream << "]";
  return stream;
}

oc::Control *allocAndFillControl(std::shared_ptr<ompl::control::SpaceInformation> si, const YAML::Node &node)
{
  oc::Control *control = si->allocControl();
  for (size_t idx = 0; idx < node.size(); ++idx)
  {
    double* address = si->getControlSpace()->getValueAddressAtIndex(control, idx);
    if (address) {
      *address = node[idx].as<double>();
    }
  }
  return control;
}

std::ofstream& printAction(std::ofstream &stream, std::shared_ptr<ompl::control::SpaceInformation> si, oc::Control *action)
{
  const size_t dim = si->getControlSpace()->getDimension();
  stream << "[";
  for (size_t d = 0; d < dim; ++d)
  {
    double *address = si->getControlSpace()->getValueAddressAtIndex(action, d);
    stream << *address;
    if (d < dim - 1)
    {
      stream << ",";
    }
  }
  stream << "]";
  return stream;
}

class Motion
{
public:
  std::vector<ob::State*> states;
  std::vector<oc::Control*> actions;

  std::shared_ptr<ShiftableDynamicAABBTreeCollisionManager<float>> collision_manager;
  std::vector<fcl::CollisionObjectf *> collision_objects;

  float cost;

  size_t idx;
  bool disabled;
};

// forward declaration
struct AStarNode;

struct compareAStarNode
{
  bool operator()(const AStarNode *a, const AStarNode *b) const;
};

// open type
typedef typename boost::heap::d_ary_heap<
    AStarNode *,
    boost::heap::arity<2>,
    boost::heap::compare<compareAStarNode>,
    boost::heap::mutable_<true>>
    open_t;

// Node type (used for open and explored states)
struct AStarNode
{
  const ob::State *state;

  float fScore;
  float gScore;

  const AStarNode* came_from;
  fcl::Vector3f used_offset;
  size_t used_motion;

  open_t::handle_type handle;
  bool is_in_open;
};

bool compareAStarNode::operator()(const AStarNode *a, const AStarNode *b) const
{
  // Sort order
  // 1. lowest fScore
  // 2. highest gScore

  // Our heap is a maximum heap, so we invert the comperator function here
  if (a->fScore != b->fScore)
  {
    return a->fScore > b->fScore;
  }
  else
  {
    return a->gScore < b->gScore;
  }
}

float heuristic(std::shared_ptr<Robot> robot, const ob::State *s, const ob::State *g)
{
  // heuristic is the time it might take to get to the goal
  Eigen::Vector3f current_pos = robot->getTransform(s).translation();
  Eigen::Vector3f goal_pos = robot->getTransform(g).translation();
  float dist = (current_pos - goal_pos).norm();
  const float max_vel = robot->maxSpeed(); // m/s
  const float time = dist / max_vel;
  return time;
}

class DBAstar
{

};

int main(int argc, char* argv[]) {
  namespace po = boost::program_options;
  // Declare the supported options.
  po::options_description desc("Allowed options");
  std::string inputFile;
  std::string motionsFile;
  float delta;
  float epsilon;
  float alpha;
  bool filterDuplicates;
  float maxCost;
  std::string outputFile;
  desc.add_options()
    ("help", "produce help message")
    ("input,i", po::value<std::string>(&inputFile)->required(), "input file (yaml)")
    ("motions,m", po::value<std::string>(&motionsFile)->required(), "motions file (yaml)")
    ("delta", po::value<float>(&delta)->default_value(0.01), "discontinuity bound (negative to auto-compute with given k)")
    ("epsilon", po::value<float>(&epsilon)->default_value(1.0), "suboptimality bound")
    ("alpha", po::value<float>(&alpha)->default_value(0.5), "alpha")
    ("filterDuplicates", po::value<bool>(&filterDuplicates)->default_value(true), "filter duplicates")
    ("maxCost", po::value<float>(&maxCost)->default_value(std::numeric_limits<float>::infinity()), "cost bound")
    ("output,o", po::value<std::string>(&outputFile)->required(), "output file (yaml)");

  try {
    po::variables_map vm;
    po::store(po::parse_command_line(argc, argv, desc), vm);
    po::notify(vm);

    if (vm.count("help") != 0u) {
      std::cout << desc << "\n";
      return 0;
    }
  } catch (po::error& e) {
    std::cerr << e.what() << std::endl << std::endl;
    std::cerr << desc << std::endl;
    return 1;
  }

  // load problem description
  YAML::Node env = YAML::LoadFile(inputFile);

  std::vector<fcl::CollisionObjectf *> obstacles;
  for (const auto &obs : env["environment"]["obstacles"])
  {
    if (obs["type"].as<std::string>() == "box")
    {
      const auto &size = obs["size"];
      std::shared_ptr<fcl::CollisionGeometryf> geom;
      geom.reset(new fcl::Boxf(size[0].as<float>(), size[1].as<float>(), 1.0));
      const auto &center = obs["center"];
      auto co = new fcl::CollisionObjectf(geom);
      co->setTranslation(fcl::Vector3f(center[0].as<float>(), center[1].as<float>(), 0));
      co->computeAABB();
      obstacles.push_back(co);
    }
    else
    {
      throw std::runtime_error("Unknown obstacle type!");
    }
  }
  std::shared_ptr<fcl::BroadPhaseCollisionManagerf> bpcm_env(new fcl::DynamicAABBTreeCollisionManagerf());
  bpcm_env->registerObjects(obstacles);
  bpcm_env->setup();

  const auto& robot_node = env["robots"][0];
  auto robotType = robot_node["type"].as<std::string>();
  const auto &env_min = env["environment"]["min"];
  const auto &env_max = env["environment"]["max"];
  ob::RealVectorBounds position_bounds(env_min.size());
  for (size_t i = 0; i < env_min.size(); ++i) {
    position_bounds.setLow(i, env_min[i].as<double>());
    position_bounds.setHigh(i, env_max[i].as<double>());
  }
  std::shared_ptr<Robot> robot = create_robot(robotType, position_bounds);

  auto si = robot->getSpaceInformation();

  // set number of control steps
  si->setPropagationStepSize(1);
  si->setMinMaxControlDuration(1, 1);

  // set state validity checking for this space
  auto stateValidityChecker(std::make_shared<fclStateValidityChecker>(si, bpcm_env, robot));
  si->setStateValidityChecker(stateValidityChecker);

  // set the state propagator
  std::shared_ptr<oc::StatePropagator> statePropagator(new RobotStatePropagator(si, robot));
  si->setStatePropagator(statePropagator);

  si->setup();

  // create and set a start state
  auto startState = allocAndFillState(si, robot_node["start"]);

  // set goal state
  auto goalState = allocAndFillState(si, robot_node["goal"]);
  // load motions primitives
  std::ifstream is( motionsFile.c_str(), std::ios::in | std::ios::binary );
  // get length of file
  is.seekg (0, is.end);
  int length = is.tellg();
  is.seekg (0, is.beg);
  //
  msgpack::unpacker unpacker;
  unpacker.reserve_buffer(length);
  is.read(unpacker.buffer(), length);
  unpacker.buffer_consumed(length);
  msgpack::object_handle oh;
  unpacker.next(oh);
  msgpack::object msg_obj = oh.get(); // size ?

  std::vector<Motion> motions;
  size_t num_states = 0;
  size_t num_invalid_states = 0;

  // create a robot with no position bounds
  ob::RealVectorBounds position_bounds_no_bound(env_min.size());
  position_bounds_no_bound.setLow(-1e6);//std::numeric_limits<double>::lowest());
  position_bounds_no_bound.setHigh(1e6);//std::numeric_limits<double>::max());
  std::shared_ptr<Robot> robot_no_pos_bound = create_robot(robotType, position_bounds_no_bound);
  auto si_no_pos_bound = robot_no_pos_bound->getSpaceInformation();
  si_no_pos_bound->setPropagationStepSize(1);
  si_no_pos_bound->setMinMaxControlDuration(1, 1);
  si_no_pos_bound->setStateValidityChecker(stateValidityChecker);
  si_no_pos_bound->setStatePropagator(statePropagator);
  si_no_pos_bound->setup();

  if (msg_obj.type != msgpack::type::ARRAY) {
    throw msgpack::type_error();
  }

  for (size_t i = 0; i < msg_obj.via.array.size; ++i) {  // what is msg_obj.via.array.size ? (5000)
    Motion m;
    // find the states
    auto item = msg_obj.via.array.ptr[i]; // what is this (size = 7, why?)
    if (item.type != msgpack::type::MAP) {
      throw msgpack::type_error();
    }
    // load the states
    for (size_t j = 0; j < item.via.map.size; ++j) { // size = 7
      auto key = item.via.map.ptr[j].key.as<std::string>();
      if (key == "states") {
        auto val = item.via.map.ptr[j].val;
        for (size_t k = 0; k < val.via.array.size; ++k) {
          ob::State* state = si->allocState();
          std::vector<double> reals;
          val.via.array.ptr[k].convert(reals);
          si->getStateSpace()->copyFromReals(state, reals);
          m.states.push_back(state);
          if (!si_no_pos_bound->satisfiesBounds(m.states.back())) {
            si_no_pos_bound->enforceBounds(m.states.back());
            ++num_invalid_states;
          }
        }
        break;
      }
    }
    num_states += m.states.size();
    // load the actions
    for (size_t j = 0; j < item.via.map.size; ++j) {
      auto key = item.via.map.ptr[j].key.as<std::string>();
      if (key == "actions") {
        auto val = item.via.map.ptr[j].val;
        for (size_t k = 0; k < val.via.array.size; ++k) {
          oc::Control *control = si->allocControl();
          std::vector<double> reals;
          val.via.array.ptr[k].convert(reals);
          for (size_t idx = 0; idx < reals.size(); ++idx) {
            double* address = si->getControlSpace()->getValueAddressAtIndex(control, idx);
            if (address) {
              *address = reals[idx];
            }
          }
          m.actions.push_back(control);
        }
        break;
      }
    }
    m.cost = m.actions.size() * robot->dt(); // time in seconds ?
    m.idx = motions.size();

    // generate collision objects and collision manager for saved motion (7 states)
    for (const auto &state : m.states)
    {
      for (size_t part = 0; part < robot->numParts(); ++part) {
        const auto &transform = robot->getTransform(state, part);

        auto co = new fcl::CollisionObjectf(robot->getCollisionGeometry(part));
        co->setTranslation(transform.translation());
        co->setRotation(transform.rotation());
        co->computeAABB();
        m.collision_objects.push_back(co);
      }
    }
    m.collision_manager.reset(new ShiftableDynamicAABBTreeCollisionManager<float>());
    m.collision_manager->registerObjects(m.collision_objects);

    m.disabled = false; // why needed ?

    motions.push_back(m); // 5000 size
  } // end of for loop, looping over all 5k motions


  std::cout << "Info: " << num_invalid_states << " states are invalid of " << num_states << std::endl;

  auto rng = std::default_random_engine{};
  std::shuffle(std::begin(motions), std::end(motions), rng);
  for (size_t idx = 0; idx < motions.size(); ++idx) {
    motions[idx].idx = idx;
  }
  std::uniform_real_distribution<> dis_angle(0, 2 * M_PI);

  // build kd-tree for motion primitives
  ompl::NearestNeighbors<Motion*>* T_m; // start states of motions
  if (si->getStateSpace()->isMetricSpace())
  {
    T_m = new ompl::NearestNeighborsGNATNoThreadSafety<Motion*>();
  } else {
    T_m = new ompl::NearestNeighborsSqrtApprox<Motion*>();
  }
  T_m->setDistanceFunction([si, motions](const Motion* a, const Motion* b) { return si->distance(a->states[0], b->states[0]); });

  for (auto& motion : motions) {
    T_m->add(&motion); // keep initial states
  }

  std::cout << "There are " << motions.size() << " motions!" << std::endl;
  std::cout << "Max cost is " << maxCost << std::endl;

  if (alpha <= 0 || alpha >= 1) {
    std::cerr << "Alpha needs to be between 0 and 1!" << std::endl;
    return 1;
  }

  //////////////////////////
  if (delta < 0) {
    Motion fakeMotion; // why needed ?
    fakeMotion.idx = -1;
    fakeMotion.states.push_back(si->allocState());
    std::vector<Motion *> neighbors_m;
    size_t num_desired_neighbors = (size_t)-delta; // ?
    size_t num_samples = std::min<size_t>(1000, motions.size());

    auto state_sampler = si->allocStateSampler();
    float sum_delta = 0.0;
    for (size_t k = 0; k < num_samples; ++k) { // why need to sample ?
      do {
        state_sampler->sampleUniform(fakeMotion.states[0]);
      } while (!si->isValid(fakeMotion.states[0]));
      robot->setPosition(fakeMotion.states[0], fcl::Vector3f(0, 0, 0));

      T_m->nearestK(&fakeMotion, num_desired_neighbors+1, neighbors_m); 

      float max_delta = si->distance(fakeMotion.states[0], neighbors_m.back()->states.front());
      sum_delta += max_delta;
    }
    float adjusted_delta = (sum_delta / num_samples) / alpha;
    std::cout << "Automatically adjusting delta to: " << adjusted_delta << std::endl;
    delta = adjusted_delta;

  }
  //////////////////////////

  if (filterDuplicates)
  {
    size_t num_duplicates = 0;
    Motion fakeMotion;
    fakeMotion.idx = -1;
    fakeMotion.states.push_back(si->allocState());
    std::vector<Motion *> neighbors_m;
    for (const auto& m : motions) {
      if (m.disabled) {
        continue;
      }

      si->copyState(fakeMotion.states[0], m.states[0]);
      T_m->nearestR(&fakeMotion, delta*alpha, neighbors_m); // finding applicable motions with discont.

      for (Motion* nm : neighbors_m) {
        if (nm == &m || nm->disabled) { // which case is it ?
          continue;
        }
        float goal_delta = si->distance(m.states.back(), nm->states.back()); // why distance between last elements ?
        if (goal_delta < delta*(1-alpha)) {
          nm->disabled = true;
          ++num_duplicates;
        }
      }
    }
    std::cout << "There are " << num_duplicates << " duplicate motions!" << std::endl;

  }

  // db-A* search
  open_t open;

  // kd-tree for nodes
  ompl::NearestNeighbors<AStarNode*> *T_n;
  if (si->getStateSpace()->isMetricSpace())
  {
    T_n = new ompl::NearestNeighborsGNATNoThreadSafety<AStarNode*>();
  }
  else
  {
    T_n = new ompl::NearestNeighborsSqrtApprox<AStarNode*>();
  }
  T_n->setDistanceFunction([si](const AStarNode* a, const AStarNode* b)
                           { return si->distance(a->state, b->state); });

  auto start_node = new AStarNode();
  start_node->state = startState;
  start_node->gScore = 0;
  start_node->fScore = epsilon * heuristic(robot, startState, goalState);
  start_node->came_from = nullptr;
  start_node->used_offset = fcl::Vector3f(0,0,0);
  start_node->used_motion = -1;

  auto handle = open.push(start_node); // what is it ?
  start_node->handle = handle;
  start_node->is_in_open = true;

  T_n->add(start_node);

  Motion fakeMotion;
  fakeMotion.idx = -1;
  fakeMotion.states.push_back(si->allocState());

  AStarNode* query_n = new AStarNode();

  ob::State* tmpState = si->allocState();
  std::vector<Motion*> neighbors_m; // applicable
  std::vector<AStarNode*> neighbors_n; // explored

  float last_f_score = start_node->fScore;
  size_t expands = 0;
  // Entering loopm while Open set is non-empty
  while (!open.empty())
  {
    AStarNode* current = open.top();
    ++expands;
    if (expands % 1000 == 0) {
      std::cout << "expanded: " << expands << " open: " << open.size() << " nodes: " << T_n->size() << " f-score " << current->fScore << std::endl;
    }
    
    // assert(current->fScore >= last_f_score);
    last_f_score = current->fScore;
    if (si->distance(current->state, goalState) <= delta) {
      std::cout << "SOLUTION FOUND !!!! cost: " << current->gScore << std::endl;

      std::vector<const AStarNode*> result;

      const AStarNode* n = current;
      while (n != nullptr) {
        result.push_back(n);
        n = n->came_from;
      }
      std::reverse(result.begin(), result.end());

      std::ofstream out(outputFile);
      out << "delta: " << delta << std::endl;
      out << "epsilon: " << epsilon << std::endl;
      out << "cost: " << current->gScore << std::endl;
      out << "result:" << std::endl;
      out << "  - states:" << std::endl;
      for (size_t i = 0; i < result.size() - 1; ++i)
      {
        // Compute intermediate states
        const auto node_state = result[i]->state;
        const fcl::Vector3f current_pos = robot->getTransform(node_state).translation();
        const auto &motion = motions.at(result[i+1]->used_motion);
        out << "      # ";
        printState(out, si, node_state);
        out << std::endl;
        out << "      # motion " << motion.idx << " with cost " << motion.cost << std::endl;
        // skip last state each
        for (size_t k = 0; k < motion.states.size(); ++k)
        {
          const auto state = motion.states[k];
          si->copyState(tmpState, state);
          const fcl::Vector3f relative_pos = robot->getTransform(state).translation();
          robot->setPosition(tmpState, current_pos + result[i+1]->used_offset + relative_pos);

          if (k < motion.states.size() - 1) {
            out << "      - ";
          } else {
            out << "      # ";
          }
          printState(out, si, tmpState);
          out << std::endl;
        }
        out << std::endl;
      } // writing result states
      out << "      - ";
      printState(out, si, result.back()->state);
      out << std::endl;
      out << "    actions:" << std::endl;
      for (size_t i = 0; i < result.size() - 1; ++i)
      {
        const auto &motion = motions[result[i+1]->used_motion];
        out << "      # motion " << motion.idx << " with cost " << motion.cost << std::endl;
        for (size_t k = 0; k < motion.actions.size(); ++k)
        {
          const auto& action = motion.actions[k];
          out << "      - ";
          printAction(out, si, action);
          out << std::endl;
        }
        out << std::endl;
      } // write actions to yaml file

      // statistics for the motions used
      std::map<size_t, size_t> motionsCount; // motionId -> usage count
      for (size_t i = 0; i < result.size() - 1; ++i)
      {
        auto motionId = result[i+1]->used_motion;
        auto iter = motionsCount.find(motionId);
        if (iter == motionsCount.end()) {
          motionsCount[motionId] = 1;
        } else {
          iter->second += 1;
        }
      }
      out << "    motion_stats:" << std::endl;
      for (const auto& kv : motionsCount) {
        out << "      " << motions[kv.first].idx << ": " << kv.second << std::endl;
      }

      // statistics on where the motion splits are
      out << "    splits:" << std::endl;
      for (size_t i = 0; i < result.size() - 1; ++i) {
        const auto &motion = motions.at(result[i+1]->used_motion);
        out << "      - " << motion.states.size() - 1 << std::endl;
      }

      return 0;
      break;
    } // if solution found things

    // If no solution then continue
    current->is_in_open = false;
    open.pop();

    // find relevant motions (within delta/2 of current state)
    si->copyState(fakeMotion.states[0], current->state);
    robot->setPosition(fakeMotion.states[0], fcl::Vector3f(0,0,0));

    T_m->nearestR(&fakeMotion, delta*alpha, neighbors_m); 
    // Loop over all potential applicable motions
    for (const Motion* motion : neighbors_m) {
      if (motion->disabled) {
        continue;
      }

#if 1
      fcl::Vector3f computed_offset(0, 0, 0);
#else
      float motion_dist = si->distance(fakeMotion.states[0], motion->states[0]);
      float translation_slack = delta/2 - motion_dist;
      assert(translation_slack >= 0);

      // ideally, solve the following optimization problem
      // min_translation fScore
      //     s.t. ||translation|| <= translation_slack // i.e., stay within delta/2
      //          no collisions

      const auto current_pos2 = robot->getTransform(current->state).translation();
      const auto goal_pos = robot->getTransform(goalState).translation();
      fcl::Vector3f computed_offset = (goal_pos - current_pos2).normalized() * translation_slack;

      #ifndef NDEBUG
      {
        // check that the computed starting state stays within delta/2
        si->copyState(tmpState, motion->states.front());
        const auto current_pos = robot->getTransform(current->state).translation();
        const auto offset = current_pos + computed_offset;
        const auto relative_pos = robot->getTransform(tmpState).translation();
        robot->setPosition(tmpState, offset + relative_pos);
        std::cout << si->distance(tmpState, current->state)  << std::endl;
        assert(si->distance(tmpState, current->state) <= delta/2 + 1e-5);
      }
      #endif
#endif

      // compute estimated cost
      float tentative_gScore = current->gScore + motion->cost;
      // compute final state -> how possible ?
      si->copyState(tmpState, motion->states.back());
      Eigen::Vector3f current_pos = robot->getTransform(current->state).translation();
      Eigen::Vector3f offset = current_pos + computed_offset;
      Eigen::Vector3f  relative_pos = robot->getTransform(tmpState).translation(); // after applying the considered motion prim.?
      robot->setPosition(tmpState, offset + relative_pos);
      // compute estimated fscore
      float tentative_hScore = epsilon * heuristic(robot, tmpState, goalState);
      float tentative_fScore = tentative_gScore + tentative_hScore;

      // skip motions that would exceed cost bound
      if (tentative_fScore > maxCost)
      {
        continue;
      }
      // skip motions that are invalid
      if (!si->satisfiesBounds(tmpState))
      {
        continue;
      }

      // Compute intermediate states and check their validity
#if 0
      bool motionValid = true;
      for (const auto& state : motion->states)
      {
        // const auto& state = motion->states.back();
        si->copyState(tmpState, state);
        const auto relative_pos = robot->getTransform(state).translation();
        robot->setPosition(tmpState, offset + relative_pos);

        // std::cout << "check";
        // si->printState(tmpState);

        if (!si->isValid(tmpState)) {
          motionValid = false;
          // std::cout << "invalid";
          break;
        }
      }
      #else
      motion->collision_manager->shift(offset); // why offset ?
      fcl::DefaultCollisionData<float> collision_data;
      motion->collision_manager->collide(bpcm_env.get(), &collision_data, fcl::DefaultCollisionFunction<float>);
      bool motionValid = !collision_data.result.isCollision();
      motion->collision_manager->shift(-offset);


#endif

      // Skip this motion, if it isn't valid
      if (!motionValid) {
        // std::cout << "skip invalid motion" << std::endl;
        continue;
      }
      // Check if we have this state (or any within delta/2) already
      query_n->state = tmpState;  // used as 'state changed with appled motion primitive' ?
      // avoid considering this an old state for very short motions
      float radius = delta*(1-alpha);
      T_n->nearestR(query_n, radius, neighbors_n);

      if (neighbors_n.size() == 0)
      // if (nearest_distance > radius)
      {
        // new state -> add it to open and T_n
        auto node = new AStarNode();
        node->state = si->cloneState(tmpState);
        node->gScore = tentative_gScore;
        node->fScore = tentative_fScore;
        node->came_from = current;
        node->used_motion = motion->idx;
        node->used_offset = computed_offset;
        node->is_in_open = true;
        auto handle = open.push(node);
        node->handle = handle;
        T_n->add(node);

      }
      else
      {
        // check if we have a better path now
        for (AStarNode* entry : neighbors_n) {
        // AStarNode* entry = nearest;
          assert(si->distance(entry->state, tmpState) <= delta);
          float delta_score = entry->gScore - tentative_gScore;
          if (delta_score > 0) {
            entry->gScore = tentative_gScore;
            entry->fScore -= delta_score;
            assert(entry->fScore >= 0);
            entry->came_from = current;
            entry->used_motion = motion->idx;
            entry->used_offset = computed_offset;
            if (entry->is_in_open) {
              open.increase(entry->handle);
            } else {
              // TODO: is this correct?
              auto handle = open.push(entry);
              entry->handle = handle;
              entry->is_in_open = true;
            }
          }
        }
      }
    }

  } // While OpenSet not empyt ends here

  query_n->state = goalState;
  const auto nearest = T_n->nearest(query_n); // why needed ?
  if (nearest->gScore == 0) {
    std::cout << "No solution found (not even approxmite)" << std::endl;
    return 1;
  }

  float nearest_distance = si->distance(nearest->state, goalState);
  std::cout << "Nearest to goal: " << nearest_distance << " (delta: " << delta << ")" << std::endl;

  std::cout << "Using approximate solution cost: " << nearest->gScore << std::endl;

  std::vector<const AStarNode*> result;

  const AStarNode* n = nearest;
  while (n != nullptr) {
    result.push_back(n);
    n = n->came_from;
  }
  std::reverse(result.begin(), result.end());

  std::ofstream out(outputFile);
  out << "delta: " << delta << std::endl;
  out << "epsilon: " << epsilon << std::endl;
  out << "cost: " << nearest->gScore << std::endl;
  out << "result:" << std::endl;
  out << "  - states:" << std::endl;
  for (size_t i = 0; i < result.size() - 1; ++i)
  {
    // Compute intermediate states
    const auto node_state = result[i]->state;
    const fcl::Vector3f current_pos = robot->getTransform(node_state).translation();
    const auto &motion = motions.at(result[i+1]->used_motion);
    out << "      # ";
    printState(out, si, node_state);
    out << std::endl;
    out << "      # motion " << motion.idx << " with cost " << motion.cost << std::endl;
    // skip last state each
    for (size_t k = 0; k < motion.states.size(); ++k)
    {
      const auto state = motion.states[k];
      si->copyState(tmpState, state);
      const fcl::Vector3f relative_pos = robot->getTransform(state).translation();
      robot->setPosition(tmpState, current_pos + result[i+1]->used_offset + relative_pos);

      if (k < motion.states.size() - 1) {
        out << "      - ";
      } else {
        out << "      # ";
      }
      printState(out, si, tmpState);
      out << std::endl;
    }
    out << std::endl;
  }
  out << "      - ";
  printState(out, si, result.back()->state);
  out << std::endl;
  out << "    actions:" << std::endl;
  for (size_t i = 0; i < result.size() - 1; ++i)
  {
    const auto &motion = motions[result[i+1]->used_motion];
    out << "      # motion " << motion.idx << " with cost " << motion.cost << std::endl;
    for (size_t k = 0; k < motion.actions.size(); ++k)
    {
      const auto& action = motion.actions[k];
      out << "      - ";
      printAction(out, si, action);
      out << std::endl;
    }
    out << std::endl;
  }
  // statistics for the motions used
  std::map<size_t, size_t> motionsCount; // motionId -> usage count
  for (size_t i = 0; i < result.size() - 1; ++i)
  {
    auto motionId = result[i+1]->used_motion;
    auto iter = motionsCount.find(motionId);
    if (iter == motionsCount.end()) {
      motionsCount[motionId] = 1;
    } else {
      iter->second += 1;
    }
  }
  out << "    motion_stats:" << std::endl;
  for (const auto& kv : motionsCount) {
    out << "      " << motions[kv.first].idx << ": " << kv.second << std::endl;
  }

  return 0;
}