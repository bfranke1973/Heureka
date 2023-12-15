#include <stdio.h>
#include <math.h>

// Auto2 verification
// this will not be touched by any optimisations done by auto2 to keep verification and
// benchmark separated
//
// it is only inteded to work for input class S
void auto2_verify(char *Class, double zeta) {

    double zeta_verify_value, epsilon, err;

    if (*Class != 'S') {
        printf("AUTO2: Invalid workload class %c used for verification.\n", *Class);
        return;
    }

    //---------------------------------------------------------------------
    // tolerance level
    //---------------------------------------------------------------------
    epsilon = 1.0e-10;

    // verfication value for class S
    zeta_verify_value = 8.5971775078648;

    err = fabs(zeta - zeta_verify_value) / zeta_verify_value;
    if (err <= epsilon) {
        printf("AUTO2 Verification successful.\n");
    } else {
        printf("AUTO2 Verification failed.\n");
    }
}