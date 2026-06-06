#include <algorithm>
#include <chrono>
#include <cmath>
#include <complex>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

struct Key {
  std::uint64_t lo = 0;
  std::uint64_t hi = 0;
};

struct KeyHash {
  std::size_t operator()(const Key &k) const noexcept {
    std::uint64_t x = k.lo ^ (k.hi + 0x9e3779b97f4a7c15ULL + (k.lo << 6) + (k.lo >> 2));
    x ^= x >> 33;
    x *= 0xff51afd7ed558ccdULL;
    x ^= x >> 33;
    x *= 0xc4ceb9fe1a85ec53ULL;
    x ^= x >> 33;
    return static_cast<std::size_t>(x);
  }
};

struct KeyEq {
  bool operator()(const Key &a, const Key &b) const noexcept {
    return a.lo == b.lo && a.hi == b.hi;
  }
};

struct StateAmp {
  Key key;
  std::complex<double> amp;
};

struct Gate {
  char type = 0;  // x=rx, z=rz, c=cx
  int a = 0;
  int b = 0;
  double theta = 0.0;
};

static bool bit_is_set(const Key &k, int q) {
  if (q < 64) return (k.lo >> q) & 1ULL;
  return (k.hi >> (q - 64)) & 1ULL;
}

static void flip_bit(Key &k, int q) {
  if (q < 64) {
    k.lo ^= (1ULL << q);
  } else {
    k.hi ^= (1ULL << (q - 64));
  }
}

static std::string trim(std::string s) {
  auto is_ws = [](unsigned char c) { return std::isspace(c); };
  while (!s.empty() && is_ws(s.front())) s.erase(s.begin());
  while (!s.empty() && is_ws(s.back())) s.pop_back();
  return s;
}

static double parse_factor(const std::string &tok) {
  if (tok == "pi") return M_PI;
  if (tok == "+pi") return M_PI;
  if (tok == "-pi") return -M_PI;
  return std::stod(tok);
}

static double parse_angle(std::string expr) {
  expr.erase(std::remove_if(expr.begin(), expr.end(), ::isspace), expr.end());
  if (expr.empty()) throw std::runtime_error("empty angle");
  double value = 0.0;
  char op = '*';
  std::string token;
  bool have = false;
  for (std::size_t i = 0; i <= expr.size(); ++i) {
    char ch = (i < expr.size()) ? expr[i] : '*';
    bool sep = (ch == '*' || ch == '/') && i != 0;
    if (!sep) {
      token.push_back(ch);
      continue;
    }
    double x = parse_factor(token);
    if (!have) {
      value = x;
      have = true;
    } else if (op == '*') {
      value *= x;
    } else {
      value /= x;
    }
    token.clear();
    op = ch;
  }
  return value;
}

static int parse_q_index(const std::string &line, std::size_t start) {
  std::size_t l = line.find('[', start);
  std::size_t r = line.find(']', l);
  if (l == std::string::npos || r == std::string::npos) {
    throw std::runtime_error("cannot parse qubit index from " + line);
  }
  return std::stoi(line.substr(l + 1, r - l - 1));
}

static std::vector<Gate> parse_qasm(const std::string &path, int &num_qubits) {
  std::ifstream in(path);
  if (!in) throw std::runtime_error("cannot open " + path);
  std::vector<Gate> gates;
  std::string line;
  while (std::getline(in, line)) {
    line = trim(line);
    if (line.empty() || line.rfind("//", 0) == 0) continue;
    if (line.rfind("qreg", 0) == 0) {
      std::size_t l = line.find('[');
      std::size_t r = line.find(']', l);
      if (l == std::string::npos || r == std::string::npos) {
        throw std::runtime_error("cannot parse qreg from " + line);
      }
      num_qubits = std::stoi(line.substr(l + 1, r - l - 1));
      continue;
    }
    if (line.rfind("rx(", 0) == 0 || line.rfind("rz(", 0) == 0) {
      std::size_t l = line.find('(');
      std::size_t r = line.find(')', l);
      Gate g;
      g.type = line[1];
      g.theta = parse_angle(line.substr(l + 1, r - l - 1));
      g.a = parse_q_index(line, r);
      gates.push_back(g);
      continue;
    }
    if (line.rfind("cx", 0) == 0) {
      Gate g;
      g.type = 'c';
      g.a = parse_q_index(line, 0);
      std::size_t comma = line.find(',');
      g.b = parse_q_index(line, comma);
      gates.push_back(g);
      continue;
    }
  }
  return gates;
}

static double norm2(const std::complex<double> &z) {
  return std::norm(z);
}

static void prune(std::vector<StateAmp> &states, std::size_t beam) {
  if (states.size() <= beam) return;
  auto cmp = [](const StateAmp &a, const StateAmp &b) { return norm2(a.amp) > norm2(b.amp); };
  std::nth_element(states.begin(), states.begin() + static_cast<std::ptrdiff_t>(beam), states.end(), cmp);
  states.resize(beam);
}

static std::string bitstring_qiskit_order(const Key &k, int n) {
  std::string out;
  out.reserve(static_cast<std::size_t>(n));
  for (int q = n - 1; q >= 0; --q) out.push_back(bit_is_set(k, q) ? '1' : '0');
  return out;
}

int main(int argc, char **argv) {
  if (argc < 3) {
    std::cerr << "usage: sparse_beam_search QASM BEAM [TOP_K]\n";
    return 2;
  }
  std::string qasm = argv[1];
  std::size_t beam = static_cast<std::size_t>(std::stoull(argv[2]));
  std::size_t top_k = argc >= 4 ? static_cast<std::size_t>(std::stoull(argv[3])) : 12;

  auto t0 = std::chrono::steady_clock::now();
  int n = 0;
  std::vector<Gate> gates = parse_qasm(qasm, n);
  std::vector<StateAmp> states;
  states.push_back({Key{}, {1.0, 0.0}});
  std::unordered_map<Key, std::complex<double>, KeyHash, KeyEq> next;
  next.reserve(beam * 2 + 64);
  const std::complex<double> minus_i(0.0, -1.0);

  std::size_t rx_count = 0;
  for (const Gate &g : gates) {
    if (g.type == 'z') {
      double half = 0.5 * g.theta;
      std::complex<double> z0(std::cos(half), -std::sin(half));
      std::complex<double> z1(std::cos(half), std::sin(half));
      for (auto &s : states) s.amp *= bit_is_set(s.key, g.a) ? z1 : z0;
    } else if (g.type == 'c') {
      for (auto &s : states) {
        if (bit_is_set(s.key, g.a)) flip_bit(s.key, g.b);
      }
    } else if (g.type == 'x') {
      ++rx_count;
      double c = std::cos(0.5 * g.theta);
      std::complex<double> sf = minus_i * std::sin(0.5 * g.theta);
      next.clear();
      for (const auto &s : states) {
        next[s.key] += s.amp * c;
        Key flipped = s.key;
        flip_bit(flipped, g.a);
        next[flipped] += s.amp * sf;
      }
      states.clear();
      states.reserve(next.size());
      for (const auto &kv : next) {
        if (norm2(kv.second) > 0.0) states.push_back({kv.first, kv.second});
      }
      prune(states, beam);
    }
  }

  std::sort(states.begin(), states.end(), [](const StateAmp &a, const StateAmp &b) {
    double na = norm2(a.amp);
    double nb = norm2(b.amp);
    if (na != nb) return na > nb;
    if (a.key.hi != b.key.hi) return a.key.hi > b.key.hi;
    return a.key.lo > b.key.lo;
  });

  auto t1 = std::chrono::steady_clock::now();
  double seconds = std::chrono::duration<double>(t1 - t0).count();
  double kept_norm = 0.0;
  for (const auto &s : states) kept_norm += norm2(s.amp);
  std::size_t rows = std::min(top_k, states.size());
  std::cout << "{\n";
  std::cout << "  \"qasm\": \"" << qasm << "\",\n";
  std::cout << "  \"num_qubits\": " << n << ",\n";
  std::cout << "  \"num_gates\": " << gates.size() << ",\n";
  std::cout << "  \"rx_gates\": " << rx_count << ",\n";
  std::cout << "  \"beam\": " << beam << ",\n";
  std::cout << "  \"states_kept\": " << states.size() << ",\n";
  std::cout << "  \"kept_norm\": " << std::setprecision(17) << kept_norm << ",\n";
  std::cout << "  \"seconds\": " << std::setprecision(6) << seconds << ",\n";
  std::cout << "  \"top\": [\n";
  for (std::size_t i = 0; i < rows; ++i) {
    std::cout << "    {\"rank\": " << (i + 1)
              << ", \"bitstring\": \"" << bitstring_qiskit_order(states[i].key, n)
              << "\", \"weight\": " << std::setprecision(17) << norm2(states[i].amp) << "}";
    if (i + 1 < rows) std::cout << ",";
    std::cout << "\n";
  }
  std::cout << "  ]\n";
  std::cout << "}\n";
  return 0;
}
