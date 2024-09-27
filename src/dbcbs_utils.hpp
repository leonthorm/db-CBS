#include <iostream>
#include <fstream>
#include <iostream>
#include <algorithm>
#include <chrono>
#include <iterator>
#include <yaml-cpp/yaml.h>
// BOOST
#include <boost/program_options.hpp>
#include <boost/heap/d_ary_heap.hpp>

#include "robots.h"
#include "robotStatePropagator.hpp"
#include "fclStateValidityChecker.hpp"
#include "fcl/broadphase/broadphase_collision_manager.h"
#include <fcl/fcl.h>
#include "planresult.hpp"
#include "nlopt.hpp"
#include "dynoplan/tdbastar/tdbastar.hpp"


void export_solution_p0(const std::vector<Eigen::VectorXf> &p0_opt, std::string outputFile_payload) { 
    
    std::ofstream out(outputFile_payload);
    out << "payload:" << std::endl;
    for (const auto& p0 : p0_opt){ 
        out << "    - [";
        out << p0(0) << ", " << p0(1) << ", " << p0(2) << "]";      
        out << std::endl;
        }
}

inline Eigen::VectorXf create_vector(const std::vector<double> &v) {
//   Eigen::VectorXf out(v.size());
//   for (size_t i = 0; i < v.size(); ++i) {
//     out(i) = v[i];
//   }
//   return out;
    std::vector<float> vf(v.begin(), v.end());
    return Eigen::Map<Eigen::VectorXf, Eigen::Unaligned>((vf.data()), vf.size());
}

inline std::vector<double> eigentoStd(const Eigen::VectorXf &eigenvec)
{
    // std::vector<double> stdvec;
    // for (const auto& i : eigenvec)
    // {
    //     stdvec.push_back(i);
    // }
    Eigen::VectorXd eigenVecD = eigenvec.cast<double>();
    std::vector<double> stdvec(&eigenVecD[0], eigenVecD.data()+eigenVecD.cols()*eigenVecD.rows());
    return stdvec;
}


typedef struct {
    std::vector<Eigen::VectorXf> pi;   // positions of the robots 
    std::vector<double> l; // cable lengths
    double mu;  // regularization weight
    double lambda; // penalty term
    Eigen::VectorXf p0_d; // Desired payload position (likely to be the previous solution)
} cost_data;


double cost(const std::vector<double> &p0, std::vector<double> &/*grad*/, void *data) {
    
    cost_data *d = (cost_data *) data; 
    const auto& pi = d -> pi;
    const auto& p0_d = d -> p0_d;
    const auto& l = d -> l;
    const auto& mu = d -> mu;
    const auto& lambda = d -> lambda;

    double cost = 0;
    double dist  = 0;
    Eigen::VectorXf p0_eigen = create_vector(p0);
    int i = 0;
    double p0z = p0_eigen(2);
    double minZ = std::numeric_limits<double>::max();
    double l_min = 0;
    for(const auto& p : pi) {
        double dist = (p0_eigen - p).norm() - l[i];
        cost += dist*dist;
        if (p(2) < minZ) {
            minZ = p(2);
            l_min = l[i];
        }
        ++i;
    }
    cost += mu*(p0_d - p0_eigen).norm() + lambda*(minZ - p0_eigen(2) - l_min)*(minZ - p0_eigen(2) - l_min);
    return cost;
}

Eigen::VectorXf optimizePayload(Eigen::VectorXf &p0_opt,
                                       size_t dim, 
                                       const Eigen::VectorXf &p0_guess, // initial guess
                                       cost_data &data
                                ) {

    // create the optimization problem
    nlopt::opt opt(nlopt::LN_COBYLA, dim);
    std::vector<double> p0_vec = eigentoStd(p0_guess);
    // set the initial guess
    opt.set_min_objective(cost, &data);
    opt.set_xtol_rel(1e-4); // Tolerance

    double minf; // Variable to store the minimum value found
    try {
        nlopt::result result = opt.optimize(p0_vec, minf);
        // std::cout << "Found minimum at f(" << p0_vec[0] << ", " << p0_vec[1] << ") = "
                //   << minf << std::endl;
        p0_opt = create_vector(p0_vec);
        return p0_opt;
    } catch (std::exception &e) {
        std::cout << "nlopt failed: " << e.what() << std::endl;
    }

}

// Cable shapes for 
struct cableShapes {
        std::vector<fcl::CollisionObjectd*> cablesObj;
        std::vector<fcl::CollisionObjectd*> robotsObj;
        std::shared_ptr<fcl::BroadPhaseCollisionManagerd> col_mgr_cables;
        std::shared_ptr<fcl::BroadPhaseCollisionManagerd> col_mgr_robots_w_realCable_l;
        std::vector<size_t> robot_indices;

    void addCableShapes(const size_t& num_robots, const std::vector<double>& l) {
        col_mgr_robots_w_realCable_l = std::make_shared<fcl::DynamicAABBTreeCollisionManagerd>();
        col_mgr_cables = std::make_shared<fcl::DynamicAABBTreeCollisionManagerd>();
        robotsObj.clear();
        cablesObj.clear();
        for (size_t i=0; i < num_robots; ++i) {
            std::shared_ptr<fcl::CollisionGeometryd> cablegeom;
            cablegeom.reset(new fcl::Capsuled(0.01, l[i]));
            cablegeom->setUserData((void*) i);
            auto cableco = new fcl::CollisionObjectd(cablegeom);
            cableco->computeAABB();
            cablesObj.push_back(cableco);

            std::shared_ptr<fcl::CollisionGeometryd> robotgeom;
            robotgeom.reset(new fcl::Sphered(0.1)); // TODO: add size of robot
            robotgeom->setUserData((void*)i);
            auto robotco = new fcl::CollisionObjectd(robotgeom);
            robotco->computeAABB();
            robotsObj.push_back(robotco);
        }
        // col_mgr_cables.reset(new fcl::DynamicAABBTreeCollisionManagerd()); 
        col_mgr_cables->registerObjects(cablesObj);
        col_mgr_cables->setup();
        
        // col_mgr_robots_w_realCable_l.reset(new fcl::DynamicAABBTreeCollisionManagerd()); 
        col_mgr_robots_w_realCable_l->registerObjects(robotsObj);
        col_mgr_robots_w_realCable_l->setup();


    }
};

// Conflicts 
struct Conflict {
  double time;
  size_t robot_idx_i;
  Eigen::VectorXd robot_state_i;
  size_t robot_idx_j;
  Eigen::VectorXd robot_state_j;
};
// Constraints
struct HighLevelNode {
    std::vector<LowLevelPlan<dynobench::Trajectory>> solution;
    std::vector<std::vector<dynoplan::Constraint>> constraints;
    float cost; 
    int id;

    typename boost::heap::d_ary_heap<HighLevelNode, boost::heap::arity<2>,
                                     boost::heap::mutable_<true> >::handle_type
        handle;
    bool operator<(const HighLevelNode& n) const {
      return cost > n.cost;
    }
};

bool getEarliestConflict(
    const std::vector<LowLevelPlan<dynobench::Trajectory>>& solution,
    const std::vector<std::shared_ptr<dynobench::Model_robot>>& all_robots,
    std::shared_ptr<fcl::BroadPhaseCollisionManagerd> col_mng_robots,
    std::vector<fcl::CollisionObjectd*>& robot_objs,
    Conflict& early_conflict,
    std::vector<double>& p0_init_guess_std,
    std::vector<Eigen::VectorXf>& p0_sol,
    const bool& solve_p0,
    const float& max_tol){
    size_t max_t = 0;
    for (const auto& sol : solution){
      max_t = std::max(max_t, sol.trajectory.states.size() - 1);
    }
    Eigen::VectorXd node_state;
    std::vector<Eigen::VectorXd> node_states;
    Eigen::VectorXf p0_opt;
    std::vector<Eigen::VectorXf> p0_tmp;
    cableShapes cables;

    std::vector<double> cable_lengths;
    for (size_t i = 0; i < all_robots.size();++i) {
        cable_lengths.push_back(0.5);
    }
    cables.addCableShapes(all_robots.size(), cable_lengths);
    Eigen::VectorXf p0_init_guess = create_vector(p0_init_guess_std);

    for (size_t t = 0; t <= max_t; ++t){
        node_states.clear();
        size_t robot_idx = 0;
        size_t obj_idx = 0;
        std::vector<fcl::Transform3d> ts_data;
        for (auto &robot : all_robots){
          if (t >= solution[robot_idx].trajectory.states.size()){
              node_state = solution[robot_idx].trajectory.states.back();    
          }
          else {
              node_state = solution[robot_idx].trajectory.states[t];
          }
          node_states.push_back(node_state);
          std::vector<fcl::Transform3d> tmp_ts(1);
          if (robot->name == "car_with_trailers") {
            tmp_ts.resize(2);
          }
          robot->transformation_collision_geometries(node_state, tmp_ts);
          ts_data.insert(ts_data.end(), tmp_ts.begin(), tmp_ts.end());
          // ts_data.insert(ts_data.end(), tmp_ts.back()); // just trailer
          ++robot_idx;
        }
        for (size_t i = 0; i < ts_data.size(); i++) {
          fcl::Transform3d &transform = ts_data[i];
          robot_objs[obj_idx]->setTranslation(transform.translation());
          robot_objs[obj_idx]->setRotation(transform.rotation());
          robot_objs[obj_idx]->computeAABB();
          ++obj_idx;
        }
        col_mng_robots->update(robot_objs);
        fcl::DefaultCollisionData<double> collision_data;
        col_mng_robots->collide(&collision_data, fcl::DefaultCollisionFunction<double>);
        if (collision_data.result.isCollision()) {
            assert(collision_data.result.numContacts() > 0);
            const auto& contact = collision_data.result.getContact(0);

            early_conflict.time = t * all_robots[0]->ref_dt;
            early_conflict.robot_idx_i = (size_t)contact.o1->getUserData();
            early_conflict.robot_idx_j = (size_t)contact.o2->getUserData();
            std::cout << "contact point 1 REGULAR CONFLICT: " << (size_t)contact.o1->getUserData() << std::endl;
            std::cout << "contact point 2 REGULAR CONFLICT: " << (size_t)contact.o2->getUserData() << std::endl;

            assert(early_conflict.robot_idx_i != early_conflict.robot_idx_j);
            early_conflict.robot_state_i = node_states[early_conflict.robot_idx_i];
            early_conflict.robot_state_j = node_states[early_conflict.robot_idx_j];
            std::cout << "CONFLICT at time " << t*all_robots[0]->ref_dt << " " << early_conflict.robot_idx_i << " " << early_conflict.robot_idx_j << std::endl;

// #ifdef DBG_PRINTS
//             std::cout << "CONFLICT at time " << t << " " << early_conflict.robot_idx_i << " " << early_conflict.robot_idx_j << std::endl;
//             auto si_i = all_robots[early_conflict.robot_idx_i]->getSpaceInformation();
//             si_i->printState(early_conflict.robot_state_i);
//             auto si_j = all_robots[early_conflict.robot_idx_j]->getSpaceInformation();
//             si_j->printState(early_conflict.robot_state_j);
// #endif
            return true;
        } 
        if (solve_p0) {
            size_t dim = 3;
            double mu = 0.18;
            double lambda = 1.;
            std::vector<Eigen::VectorXf> pi;
            std::vector<double> li;
            for (const auto& robot_obj : robot_objs) {
                Eigen::Vector3f robot_pos = robot_obj->getTranslation().cast<float>();
                pi.push_back(create_vector({robot_pos(0), robot_pos(1), robot_pos(2)}));
                li.push_back(0.5);
            }
            cost_data data {pi, li, mu, lambda, p0_init_guess}; // prepare the data for the opt
            optimizePayload(p0_opt, dim, p0_init_guess, data);
            p0_init_guess << p0_opt(0), p0_opt(1), p0_opt(2);
            size_t robot_counter = 0;
            for (const auto& p : pi) {
                float distance = (p - p0_opt).norm();
                double tol = abs(distance - li[robot_counter]);

                if (tol > max_tol) {
                    std::cout << "robot_id: "<< robot_counter << ", tol: " << tol  << std::endl;
                    std::cout << "p: \n" << pi[robot_counter] << "\np0: \n" << p0_opt << std::endl;
                    early_conflict.time = t * all_robots[0]->ref_dt;
                    early_conflict.robot_idx_i = robot_counter; 
                    early_conflict.robot_state_i = node_states[early_conflict.robot_idx_i];
                    std::cout << "CONFLICT at time " << t*all_robots[0]->ref_dt << " " << early_conflict.robot_idx_i << std::endl;
                    early_conflict.robot_idx_j = 99;
                    // early_conflict.robot_state_j = node_states[early_conflict.robot_idx_j];
                    assert(early_conflict.robot_idx_i != early_conflict.robot_idx_j);
                    return true;
                }
            ++robot_counter;
            }
            // artificial cables and robots collision checker
            // creates a conflict if a cable is in collision with the environment
            // The length of the cable is adjusted based on the position of the robot and the 
            // optimized payload position.
            // on the other hand, the robots positions are updated using the actual lengths of the cables (0.5 m)
            // and the payload position.
            // and the conflict exists if inter-robot collision takes place 
 
            size_t num_robots = all_robots.size(); 
            cables.cablesObj.clear();
            for (size_t i=0; i < num_robots; ++i) {
                Eigen::Vector3d qi = (p0_opt.cast<double>() - pi[i].cast<double>()).normalized();
                double cable_l =  (p0_opt.cast<double>() - pi[i].cast<double>()).norm();
                
                std::shared_ptr<fcl::CollisionGeometryd> cablegeom(new fcl::Capsuled(0.01, cable_l));
                auto cableco = new fcl::CollisionObjectd(cablegeom);            
                Eigen::Vector3d cable_pos = p0_opt.cast<double>() - 0.5*cable_l*qi;
                Eigen::Vector3d from(0., 0., -1.);
                Eigen::Vector4d cable_quat(Eigen::Quaternion<double>::FromTwoVectors(from, qi).coeffs());
                
                fcl::Transform3d result;
                result = Eigen::Translation<double, 3>(cable_pos);
                result.rotate(Eigen::Quaterniond(cable_quat));
                cableco->setTransform(result);
                delete cables.cablesObj[i];
                cables.cablesObj[i] = cableco;
                cables.cablesObj[i]->computeAABB();                

                fcl::Transform3d result_robot;
                Eigen::Vector3d robot_pos_fake(p0_opt.cast<double>() - li[i]*qi);
                result_robot = Eigen::Translation<double, 3>(robot_pos_fake);
                cables.robotsObj[i]->setTransform(result_robot);
                cables.robotsObj[i]->computeAABB();
            }

            cables.col_mgr_cables->clear();
            cables.col_mgr_cables->registerObjects(cables.cablesObj);
            cables.col_mgr_cables->setup();
            cables.col_mgr_cables->update(cables.cablesObj);
            fcl::DefaultCollisionData<double> cable_collision_data;

            cables.col_mgr_robots_w_realCable_l->update(cables.robotsObj);
            fcl::DefaultCollisionData<double> robots_collision_data;
        

            cables.col_mgr_cables->collide(all_robots[0]->env.get(), &cable_collision_data,
                                     fcl::DefaultCollisionFunction<double>);
            if (t == 0) {
                std::cout << "cable/environment collision check: " << all_robots[0]->env.get() << std::endl;
            }
            cables.col_mgr_robots_w_realCable_l->collide(&robots_collision_data,
                                        fcl::DefaultCollisionFunction<double>);

            if (cable_collision_data.result.isCollision()) {
                const auto& contact = cable_collision_data.result.getContact(0);
                std::cout << "cable collision exists: \n" << "cables: " <<  cable_collision_data.result.isCollision()  << std::endl;
                early_conflict.time = t * all_robots[0]->ref_dt;
                early_conflict.robot_idx_i = (size_t)contact.o1->getUserData();
                early_conflict.robot_idx_j = 99;
                std::cout << "cable id 1:" << (size_t)contact.o1->getUserData() << std::endl;
                std::cout << "cable id 2:" << (size_t)contact.o2->getUserData() << std::endl;
                assert(early_conflict.robot_idx_i != early_conflict.robot_idx_j);
                early_conflict.robot_state_i = node_states[early_conflict.robot_idx_i];
                // early_conflict.robot_state_j = node_states[early_conflict.robot_idx_j];
                return true;
            }

            if (robots_collision_data.result.isCollision()) {
                const auto& contact = robots_collision_data.result.getContact(0);
                // std::cout << "collision exists: \n" << "cables: " <<  cable_collision_data.result.isCollision() 
                std::cout << "robot collision exists: \n" << " robots: " << robots_collision_data.result.isCollision() << std::endl;
                early_conflict.time = t * all_robots[0]->ref_dt;
                early_conflict.robot_idx_i = (size_t)contact.o1->getUserData();
                early_conflict.robot_idx_j = (size_t)contact.o2->getUserData();
                std::cout << "id 1:" << (size_t)contact.o1->getUserData() << std::endl;
                std::cout << "id 2:" << (size_t)contact.o2->getUserData() << std::endl;
                assert(early_conflict.robot_idx_i != early_conflict.robot_idx_j);
                early_conflict.robot_state_i = node_states[early_conflict.robot_idx_i];
                early_conflict.robot_state_j = node_states[early_conflict.robot_idx_j];
                return true;
            }
            p0_tmp.push_back(p0_opt);        
        }
    }
    if (solve_p0) {
        for (const auto& p0i : p0_tmp) {
            p0_sol.push_back(p0i);
        }
    }
    return false;

}

void createConstraintsFromConflicts(const Conflict& early_conflict, std::map<size_t, std::vector<dynoplan::Constraint>>& constraints){
    constraints[early_conflict.robot_idx_i].push_back({early_conflict.time, early_conflict.robot_state_i});
    if (early_conflict.robot_idx_j != 99) {
        constraints[early_conflict.robot_idx_j].push_back({early_conflict.time, early_conflict.robot_state_j});
    } 
}

void export_solutions(const std::vector<LowLevelPlan<dynobench::Trajectory>>& solution, 
                        const int robot_numx, std::ofstream *out, int & expansions){
    float cost = 0;
    for (auto& n : solution)
      cost += n.trajectory.cost;
    *out << "cost: " << cost << std::endl; 
    *out << "expansions: " << expansions << std::endl;
    *out << "result:" << std::endl;
    for (size_t i = 0; i < solution.size(); ++i){ 
        std::vector<Eigen::VectorXd> tmp_states = solution[i].trajectory.states;
        std::vector<Eigen::VectorXd> tmp_actions = solution[i].trajectory.actions;
        *out << "  - states:" << std::endl;
        for (size_t j = 0; j < tmp_states.size(); ++j){
            *out << "      - ";
            *out << tmp_states.at(j).format(dynobench::FMT)<< std::endl;
        }
        *out << "    actions:" << std::endl;
        for (size_t j = 0; j < tmp_actions.size(); ++j){
            *out << "      - ";
            *out << tmp_actions.at(j).format(dynobench::FMT)<< std::endl;
            
        }
    }
}
