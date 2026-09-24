// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_EXPRESSION_H
#define LEFONY_EXPRESSION_H
#include "math.h"
#include <stddef.h>

// Experimental bounded scalar expressions. All state and computation live in
// the app. This deliberately does not access Poincare or OS calculator variables.
namespace Lefony { namespace Expression {
enum class Status { Ok, Invalid, Limit, Unbound, Domain, Cancelled, Stale, Unsupported };
class Context;
struct Handle { const Context *owner; uint32_t generation; uint16_t node; };
struct Parsed { Status status; uint16_t position; Handle expression; };
struct Evaluated { Status status; uint16_t position; double value; uint16_t steps; };
class Context {
public:
  static constexpr unsigned MaximumSource=256, MaximumNodes=128, MaximumDepth=16, MaximumVariables=16;
  constexpr Context() : m_nodes{},m_variables{},m_count(0),m_variableCount(0),m_generation(0),
    m_source(nullptr),m_length(0),m_offset(0),m_depth(0),m_status(Status::Invalid),m_error(0),m_angle(Math::Angle::Radians) {}
  bool angle(Math::Angle mode) {
    if(mode!=Math::Angle::Radians && mode!=Math::Angle::Degrees && mode!=Math::Angle::Gradians) return false;
    m_angle=mode;return true;
  }
  Math::Angle angle() const { return m_angle; }
  bool set(const char *name,double value) {
    unsigned size=0;if(!name || !Numeric::finite(value)) return false;
    while(size<16 && name[size]) { if(!letter(name[size]) && !(size && digit(name[size]))) return false;size++; }
    if(!size || size>15 || reserved(name)) return false;
    for(unsigned i=0;i<m_variableCount;i++) if(equal(m_variables[i].name,name)) { m_variables[i].value=value;return true; }
    if(m_variableCount==MaximumVariables) return false;
    for(unsigned i=0;i<=size;i++) m_variables[m_variableCount].name[i]=name[i];
    m_variables[m_variableCount++].value=value;return true;
  }
  void clearVariables() { m_variableCount=0; }
  Parsed parse(const char *source,size_t size) {
    // Every attempt invalidates previous handles, including failed parses.
    m_count=0;m_offset=0;m_depth=0;m_error=0;m_status=Status::Ok;
    if(m_generation==UINT32_MAX) return {Status::Limit,0,{this,0,0}};
    m_generation++;
    if(!source || !size || size>MaximumSource) return {size>MaximumSource?Status::Limit:Status::Invalid,0,{this,0,0}};
    m_source=source;m_length=static_cast<unsigned>(size);
    uint16_t node=sum();space();
    if(m_status==Status::Ok && m_offset!=m_length) fail(Status::Invalid);
    Parsed result{m_status,static_cast<uint16_t>(m_error),{this,m_generation,node}};
    if(m_status!=Status::Ok) m_count=0;
    m_source=nullptr;m_length=0;return result;
  }
  template<typename Cancel> Evaluated evaluate(Handle handle,Cancel cancel) const {
    if(handle.owner!=this || handle.generation!=m_generation || handle.node>=m_count) return {Status::Stale,0,0,0};
    double values[MaximumNodes]{};
    for(unsigned i=0;i<=handle.node;i++) {
      const Node &node=m_nodes[i];
      if(cancel()) return {Status::Cancelled,node.position,0,static_cast<uint16_t>(i)};
      double a=node.left<i?values[node.left]:0,b=node.right<i?values[node.right]:0,value=0;
      switch(node.kind) {
        case Kind::Constant:value=node.value;break;
        case Kind::Variable: {
          bool found=false;
          for(unsigned j=0;j<m_variableCount;j++) if(equal(node.name,m_variables[j].name)) { value=m_variables[j].value;found=true;break; }
          if(!found) return {Status::Unbound,node.position,0,static_cast<uint16_t>(i+1)};
          break;
        }
        case Kind::Add:value=a+b;break;
        case Kind::Subtract:value=a-b;break;
        case Kind::Multiply:value=a*b;break;
        case Kind::Divide:
          if(b==0) return {Status::Domain,node.position,0,static_cast<uint16_t>(i+1)};
          value=a/b;break;
        case Kind::Negate:value=-a;break;
        case Kind::Abs:value=Numeric::abs(a);break;
        case Kind::Sqrt:value=Math::sqrt(a);break;
        case Kind::Sin:value=Math::sin(Math::radians(a,m_angle));break;
        case Kind::Cos:value=Math::cos(Math::radians(a,m_angle));break;
        case Kind::Tan:value=Math::tan(Math::radians(a,m_angle));break;
        case Kind::Asin:value=angleResult(Math::asin(a));break;
        case Kind::Acos:value=angleResult(Math::acos(a));break;
        case Kind::Atan:value=angleResult(Math::atan(a));break;
        case Kind::Exp:value=Math::exp(a);break;
        case Kind::Log:value=Math::log(a);break;
        case Kind::Log10:value=Math::log10(a);break;
        case Kind::Log2:value=Math::log2(a);break;
        case Kind::Floor:value=Math::floor(a);break;
        case Kind::Ceil:value=Math::ceil(a);break;
        case Kind::Round:value=Math::round(a);break;
        case Kind::Erf:value=Math::erf(a);break;
        case Kind::Power: {
          if(a==0 && b<=0) return {Status::Domain,node.position,0,static_cast<uint16_t>(i+1)};
          value=Math::pow(a,b);break;
        }
      }
      if(!Numeric::finite(value)) return {Status::Domain,node.position,0,static_cast<uint16_t>(i+1)};
      values[i]=value;
    }
    return {Status::Ok,0,values[handle.node],static_cast<uint16_t>(handle.node+1)};
  }
  Evaluated evaluate(Handle handle) const { return evaluate(handle,[](){return false;}); }
  unsigned nodes() const { return m_count; }
private:
  enum class Kind : uint8_t { Constant,Variable,Add,Subtract,Multiply,Divide,Negate,Abs,Sqrt,Power,
    Sin,Cos,Tan,Asin,Acos,Atan,Exp,Log,Log10,Log2,Floor,Ceil,Round,Erf };
  struct Node { Kind kind;uint16_t left,right,position;double value;char name[16]; };
  struct Variable { char name[16];double value; };
  static bool letter(char c) { return (c>='a' && c<='z') || (c>='A' && c<='Z'); }
  static bool digit(char c) { return c>='0' && c<='9'; }
  static bool equal(const char *a,const char *b) { for(unsigned i=0;i<16;i++) { if(a[i]!=b[i]) return false;if(!a[i]) return true; }return false; }
  static Kind function(const char *name) {
    struct Entry { const char *name;Kind kind; };
    constexpr Entry functions[]={
      {"abs",Kind::Abs},{"sqrt",Kind::Sqrt},{"sin",Kind::Sin},{"cos",Kind::Cos},{"tan",Kind::Tan},
      {"asin",Kind::Asin},{"acos",Kind::Acos},{"atan",Kind::Atan},{"exp",Kind::Exp},{"ln",Kind::Log},
      {"log",Kind::Log},{"log10",Kind::Log10},{"log2",Kind::Log2},{"floor",Kind::Floor},
      {"ceil",Kind::Ceil},{"round",Kind::Round},{"erf",Kind::Erf}};
    for(const auto &entry:functions) if(equal(name,entry.name)) return entry.kind;
    return Kind::Variable;
  }
  static bool reserved(const char *name) { return function(name)!=Kind::Variable || equal(name,"pi") || equal(name,"e"); }
  double angleResult(double value) const { return m_angle==Math::Angle::Degrees?Math::degrees(value):m_angle==Math::Angle::Gradians?Math::gradians(value):value; }
  char peek() const { return m_offset<m_length?m_source[m_offset]:0; }
  void space() { while(m_offset<m_length && (peek()==' ' || peek()=='\t' || peek()=='\n' || peek()=='\r')) m_offset++; }
  void fail(Status status) { if(m_status==Status::Ok) { m_status=status;m_error=m_offset; } }
  bool enter() { if(m_depth==MaximumDepth) { fail(Status::Limit);return false; }m_depth++;return true; }
  uint16_t add(Kind kind,unsigned position,uint16_t left=0,uint16_t right=0,double value=0) {
    if(m_status!=Status::Ok) return 0;
    if(m_count==MaximumNodes) { fail(Status::Limit);return 0; }
    unsigned index=m_count++;m_nodes[index]={kind,left,right,static_cast<uint16_t>(position),value,{}};return static_cast<uint16_t>(index);
  }
  uint16_t sum() {
    uint16_t left=product();space();
    while(m_status==Status::Ok && (peek()=='+' || peek()=='-')) {
      char op=peek();unsigned position=m_offset++;uint16_t right=product();
      left=add(op=='+'?Kind::Add:Kind::Subtract,position,left,right);space();
    }
    return left;
  }
  uint16_t product() {
    uint16_t left=unary();space();
    while(m_status==Status::Ok && (peek()=='*' || peek()=='/')) {
      char op=peek();unsigned position=m_offset++;uint16_t right=unary();
      left=add(op=='*'?Kind::Multiply:Kind::Divide,position,left,right);space();
    }
    return left;
  }
  uint16_t unary() {
    if(m_status!=Status::Ok || !enter()) return 0;
    space();unsigned position=m_offset;uint16_t node;
    if(peek()=='+' || peek()=='-') { char sign=peek();m_offset++;node=unary();if(sign=='-') node=add(Kind::Negate,position,node); }
    else {
      node=primary();space();
      if(peek()=='^') { position=m_offset++;uint16_t right=unary();node=add(Kind::Power,position,node,right); }
    }
    m_depth--;return node;
  }
  uint16_t primary() {
    space();unsigned position=m_offset;
    if(peek()=='(') { m_offset++;uint16_t node=sum();space();if(peek()!=')') fail(Status::Invalid);else m_offset++;return node; }
    if(digit(peek()) || peek()=='.') return number();
    if(letter(peek())) {
      char name[16]{};unsigned length=0;
      while(letter(peek()) || digit(peek())) { if(length==15) { fail(Status::Limit);return 0; }name[length++]=peek();m_offset++; }
      space();
      if(peek()=='(') {
        Kind kind=function(name);
        if(kind==Kind::Variable) { fail(Status::Unsupported);return 0; }
        m_offset++;uint16_t arg=sum();space();
        if(peek()!=')') fail(Status::Invalid);else m_offset++;
        return add(kind,position,arg);
      }
      if(equal(name,"pi") || equal(name,"e")) return add(Kind::Constant,position,0,0,equal(name,"pi")?Math::Pi:Math::E);
      if(reserved(name)) { fail(Status::Invalid);return 0; }
      uint16_t node=add(Kind::Variable,position);
      if(m_status==Status::Ok) for(unsigned i=0;i<=length;i++) m_nodes[node].name[i]=name[i];
      return node;
    }
    fail(Status::Invalid);return 0;
  }
  uint16_t number() {
    unsigned position=m_offset,digits=0;double value=0,fraction=0.1;
    while(digit(peek())) { value=value*10+(peek()-'0');m_offset++;digits++; }
    if(peek()=='.') {
      m_offset++;
      while(digit(peek())) { value+=(peek()-'0')*fraction;fraction*=0.1;m_offset++;digits++; }
    }
    if(!digits) { fail(Status::Invalid);return 0; }
    if(peek()=='e' || peek()=='E') {
      m_offset++;bool negative=peek()=='-';if(peek()=='+' || peek()=='-') m_offset++;
      if(!digit(peek())) { fail(Status::Invalid);return 0; }
      unsigned exponent=0;
      while(digit(peek())) { exponent=exponent*10+(peek()-'0');m_offset++;if(exponent>308) { fail(Status::Limit);return 0; } }
      for(unsigned i=0;i<exponent;i++) value=negative?value/10:value*10;
    }
    if(!Numeric::finite(value)) { fail(Status::Domain);return 0; }
    return add(Kind::Constant,position,0,0,value);
  }
  Node m_nodes[MaximumNodes];Variable m_variables[MaximumVariables];
  unsigned m_count,m_variableCount;uint32_t m_generation;
  const char *m_source;unsigned m_length,m_offset,m_depth;Status m_status;unsigned m_error;Math::Angle m_angle;
};
}}
#endif
