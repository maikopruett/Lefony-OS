# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared high-precision numeric fixtures for host and real ARM qualification."""
import math
import random
from pathlib import Path
import shutil
import subprocess
import mpmath as mp

OPS = ['sin','cos','tan','asin','acos','atan','sqrt','exp','expm1','log','log1p','log10','log2',
       'erf','erfc','abs','floor','ceil','trunc','round','atan2','pow','hypot','fmod','copySign','nextAfter']


def build_objects(destination):
    sdk = Path(__file__).resolve().parents[1] / 'sdk'
    cc = shutil.which('cc')
    if not cc:
        raise RuntimeError('C compiler unavailable')
    objects = []
    for source in sorted((sdk / 'lib/vendor/openbsd-math').glob('*.c')):
        obj = destination / (source.stem + '.o');objects.append(str(obj))
        subprocess.run([cc, '-std=c11', '-O1', '-ffreestanding', '-ffp-contract=off', '-fno-strict-aliasing', '-fwrapv',
                        '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-w',
                        '-I', str(sdk / 'lib/math_compat'), '-c', str(source), '-o', str(obj)], check=True, timeout=30)
    return objects


def vectors():
    rng = random.Random(20260911)
    cases = []
    with mp.workdps(400):
        def add(name, a, b, expected):
            expected = float(expected)
            if not math.isfinite(expected):
                return
            tolerance = 8 * math.ulp(expected)
            cases.append((OPS.index(name), float(a), float(b), expected, tolerance))

        trig = [0.,-0.,1e-300,-1e-20,.125,-.5,1.,-1.,math.pi/2,math.pi,1000.,1e10,1e100,1e300,
                float.fromhex('0x1.fffffffffffffp+1023')] + [rng.uniform(-100,100) for _ in range(25)]
        positive = [float.fromhex('0x0.0000000000001p-1022'),1e-308,1e-200,.01,.5,1.,2.,10.,1e100,1e300,
                    float.fromhex('0x1.fffffffffffffp+1023')] + [10**rng.uniform(-300,300) for _ in range(20)]
        ordinary = [-100.,-4.5,-3.25,-.5,-.1,-0.,0.,.1,.5,1.,2.5,4.25,100.] + [rng.uniform(-100,100) for _ in range(20)]
        for name in ('sin','cos','tan','atan'):
            for a in trig: add(name,a,0,getattr(mp,name)(mp.mpf(a)))
        for name in ('asin','acos'):
            for a in [-1.,-.9999999999999999,-.5,-0.,0.,.5,.9999999999999999,1.] + [rng.uniform(-1,1) for _ in range(20)]:
                add(name,a,0,getattr(mp,name)(mp.mpf(a)))
        for name in ('sqrt','log','log10','log2'):
            for a in positive:
                value = mp.sqrt(a) if name=='sqrt' else mp.log(a,10) if name=='log10' else mp.log(a,2) if name=='log2' else mp.log(a)
                add(name,a,0,value)
        for name in ('exp','expm1'):
            for a in [-745.,-744.,-700.,-1.,-1e-20,0.,1e-20,1.,10.,700.] + [rng.uniform(-700,700) for _ in range(20)]:
                add(name,a,0,getattr(mp,name)(mp.mpf(a)))
        for a in [-.9999999999999999,-.5,-1e-20,-0.,0.,1e-20,.5,1.,100.,1e300]: add('log1p',a,0,mp.log1p(a))
        for name in ('erf','erfc'):
            for a in [-27.,-10.,-2.,-1.,-1e-15,-0.,0.,1e-15,.5,1.,2.,10.,27.] + [rng.uniform(-8,8) for _ in range(20)]:
                add(name,a,0,getattr(mp,name)(mp.mpf(a)))
        for a in ordinary:
            value=mp.mpf(a)
            add('abs',a,0,abs(value));add('floor',a,0,mp.floor(value));add('ceil',a,0,mp.ceil(value))
            add('trunc',a,0,mp.floor(value) if value>=0 else mp.ceil(value))
            add('round',a,0,mp.floor(value+mp.mpf('.5')) if value>=0 else -mp.floor(-value+mp.mpf('.5')))
        for a,b in [(0.,1.),(1.,0.),(-1.,0.),(1.,-1.),(-1.,-1.),(1e300,1e-300)] + [(rng.uniform(-100,100),rng.uniform(-100,100)) for _ in range(20)]:
            add('atan2',a,b,mp.atan2(a,b))
        for a,b in [(2.,.5),(2.,32.25),(.25,-1.5),(-2.,3.),(-2.,-3.),(.999,10000.),(1e-200,1.5),(1e200,.5),(0.,2.),(2.,0.)] + [(10**rng.uniform(-5,5),rng.uniform(-10,10)) for _ in range(20)]:
            add('pow',a,b,mp.power(a,b))
        for a,b in [(3.,4.),(-3.,4.),(1e308,1e308),(1e-308,1e-308),(1e300,1e-300)] + [(rng.uniform(-100,100),rng.uniform(-100,100)) for _ in range(20)]:
            add('hypot',a,b,mp.sqrt(mp.mpf(a)**2+mp.mpf(b)**2))
        for a,b in [(7.25,2.),(-7.25,2.),(7.25,-2.),(1e300,3.),(1e-300,1e-301)] + [(rng.uniform(-100,100),rng.uniform(.1,10)) for _ in range(20)]:
            quotient=mp.mpf(a)/mp.mpf(b);integer=mp.floor(quotient) if quotient>=0 else mp.ceil(quotient)
            add('fmod',a,b,mp.mpf(a)-integer*mp.mpf(b))
        for a,b in [(2.,-4.),(-2.,4.),(0.,-1.),(-0.,1.),(1e300,-1.),(1e-300,-1.)]: add('copySign',a,b,math.copysign(a,b))
        for a,b in [(0.,1.),(0.,-1.),(1.,2.),(1.,0.),(-1.,0.),(1e300,0.),(1e-300,0.)]: add('nextAfter',a,b,math.nextafter(a,b))
    return cases


def cpp(arm=False):
    rows = ',\n'.join('{%d,%s,%s,%s,%s}' % (op,a.hex(),b.hex(),value.hex(),tolerance.hex())
                       for op,a,b,value,tolerance in vectors())
    switches = '\n'.join(f'case {i}: actual=Lefony::Math::{name}(c.a' + (',c.b' if i>=20 else '') + ');break;'
                         for i,name in enumerate(OPS))
    source = '''#include <lefony/math.h>
#include <stdint.h>
struct Case { unsigned op;double a,b,expected,tolerance; };
static const Case cases[]={ROWS};
static unsigned failed=0;
static double got=0,wanted=0;
static bool testMath() {
  unsigned index=0;
  for(const auto &c:cases) {
    double actual=0;switch(c.op) { SWITCHES }
    double delta=actual-c.expected;double error=delta<0?-delta:delta;
    if(!__builtin_isfinite(actual) || error>c.tolerance) { failed=index;got=actual;wanted=c.expected;return false; }
    index++;
  }
  using namespace Lefony::Math;
  double whole=0;int exponent=0;
  if(fraction(-3.25,whole)!=-.25 || whole!=-3 || fractionExponent(12,exponent)!=.75 || exponent!=4) return false;
  if(scale(1.5,4)!=24 || scale(1,-1074)!=0x0.0000000000001p-1022 || scale(1,INT32_MIN)!=0) return false;
  if(!__builtin_isinf(exp(1000)) || !__builtin_isnan(sqrt(-1)) || !__builtin_isnan(log(-1)) || !__builtin_isnan(pow(-2,.5))) return false;
  if(!__builtin_signbit(sin(-0.)) || !__builtin_signbit(sqrt(-0.)) || __builtin_signbit(abs(-0.))) return false;
  if(atan2(-0.,-1)!=-Pi || round(-.5)!=-1 || pow(0,0)!=1) return false;
  if(checked(sqrt(-1)).status!=Lefony::Numeric::Status::Domain || checked(7).status!=Lefony::Numeric::Status::Ok) return false;
  if(radians(180,Angle::Degrees)!=Pi || degrees(Pi)!=180 || !__builtin_isnan(radians(1,static_cast<Angle>(99)))) return false;
  return true;
}
'''.replace('ROWS',rows).replace('SWITCHES',switches)
    if arm:
        return source + '''#include <lefony/app.h>
extern "C" void lefony_event(Lefony::Event event,uint32_t,uint32_t) {
  if(event==Lefony::Event::Start && !testMath()) asm volatile("udf #0");
}
'''
    return source + '''#include <cstdio>
int main() { if(!testMath()) { std::fprintf(stderr,"case %u: got %.17g, expected %.17g\\n",failed,got,wanted);return 1; }
std::printf("%zu high-precision cases and helper/domain checks passed\\n",sizeof(cases)/sizeof(cases[0])); }
'''
