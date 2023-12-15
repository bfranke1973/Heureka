#include <stdio.h>
#include <math.h>

#define EPSILON   1.0e-8

typedef enum { false, true } logical;

// Auto2 verification
// this will not be touched by any optimisations done by auto2 to keep verification and
// benchmark separated
//
// it is only inteded to work for input class S
void auto2_verify(char Class, double sx, double sy) {

    double sx_verify_value, sy_verify_value, sx_err, sy_err;
    logical verified;

    if (Class != 'S') {
        printf("AUTO2: Invalid workload class %c used for verification.\n", Class);
        return;
    }

    verified = true;

    // verfication values for class S
    sx_verify_value = -3.247834652034740e+3;
    sy_verify_value = -6.958407078382297e+3;

    sx_err = fabs((sx - sx_verify_value) / sx_verify_value);
    sy_err = fabs((sy - sy_verify_value) / sy_verify_value);
    verified = ((sx_err <= EPSILON) && (sy_err <= EPSILON));

    if (verified) {
        printf("AUTO2 Verification successful.\n");
    } else {
        printf("AUTO2 Verification failed.\n");
    }
}