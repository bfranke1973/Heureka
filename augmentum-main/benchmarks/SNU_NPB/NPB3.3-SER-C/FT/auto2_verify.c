#include <stdio.h>
#include <math.h>

// from type.h
typedef enum { false, true } logical;
typedef struct { 
  double real;
  double imag;
} dcomplex;

// from global.h
#define dcmplx(r,i)       (dcomplex){r, i}
#define dcmplx_sub(a,b)   (dcomplex){(a).real-(b).real, (a).imag-(b).imag}

static inline dcomplex dcmplx_div(dcomplex z1, dcomplex z2) {
  double a = z1.real;
  double b = z1.imag;
  double c = z2.real;
  double d = z2.imag;

  double divisor = c*c + d*d;
  double real = (a*c + b*d) / divisor;
  double imag = (b*c - a*d) / divisor;
  dcomplex result = (dcomplex){real, imag};
  return result;
}
#define dcmplx_abs(x)     sqrt(((x).real*(x).real) + ((x).imag*(x).imag))

// Auto2 verification
// this will not be touched by any optimisations done by auto2 to keep verification and
// benchmark separated
//
// it is only inteded to work for input class S and W
void auto2_verify(int n1, int n2, int n3, int nt, dcomplex cksum[nt+1]) {

    // Local variables.
    int kt;
    dcomplex cexpd[25+1];
    double epsilon, err;

    // Initialize tolerance level and success flag.
    epsilon = 1.0e-12;
    logical verified = true;


    if ((n1 == 64) && (n2 == 64) && (n3 == 64) && (nt == 6)) {
        // Class S reference values.
        cexpd[1] = dcmplx(554.6087004964, 484.5363331978);
        cexpd[2] = dcmplx(554.6385409189, 486.5304269511);
        cexpd[3] = dcmplx(554.6148406171, 488.3910722336);
        cexpd[4] = dcmplx(554.5423607415, 490.1273169046);
        cexpd[5] = dcmplx(554.4255039624, 491.7475857993);
        cexpd[6] = dcmplx(554.2683411902, 493.2597244941);        
    } else if ((n1 == 128) && (n2 == 128) && (n3 == 32) && (nt == 6)) {
        // Class W reference values.
        cexpd[1] = dcmplx(567.3612178944, 529.3246849175);
        cexpd[2] = dcmplx(563.1436885271, 528.2149986629);
        cexpd[3] = dcmplx(559.4024089970, 527.0996558037);
        cexpd[4] = dcmplx(556.0698047020, 526.0027904925);
        cexpd[5] = dcmplx(553.0898991250, 524.9400845633);
        cexpd[6] = dcmplx(550.4159734538, 523.9212247086);
    } else {
        printf("AUTO2: Invalid workload class used for verification.\n");
        return;
    }

    // Verification test for results.
    for (kt = 1; kt <= nt; kt++) {
        err = dcmplx_abs(dcmplx_div(dcmplx_sub(cksum[kt], cexpd[kt]),
                                    cexpd[kt]));
        if (!(err <= epsilon)) {
            verified = false;
            break;
        }
    }

    if (verified) {
      printf("AUTO2 Verification successful.\n");
    } else {
      printf("AUTO2 Verification failed.\n");
    }
}