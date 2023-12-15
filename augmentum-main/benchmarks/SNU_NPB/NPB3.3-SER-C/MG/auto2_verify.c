#include <stdio.h>
#include <math.h>

// Auto2 verification
// this will not be touched by any optimisations done by auto2 to keep verification and
// benchmark separated
//
// it is only inteded to work for input class S
void auto2_verify(char* Class, double rnm2) {

    double epsilon, err, verify_value;

    if (*Class != 'S') {
        printf("AUTO2: Invalid workload class %c used for verification.\n", *Class);
        return;
    }

    epsilon = 1.0e-8;
    verify_value = 0.5307707005734e-04;

    err = fabs( rnm2 - verify_value ) / verify_value;
    if (err <= epsilon) {
        printf("AUTO2 Verification successful.\n");
    } else {
        printf("AUTO2 Verification failed.\n");
    }
}