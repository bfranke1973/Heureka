#include <stdio.h>
#include <math.h>

typedef enum { false, true } logical;

// Auto2 verification
// this will not be touched by any optimisations done by auto2 to keep verification and
// benchmark separated
//
// it is only inteded to work for input class S
void auto2_verify(char *Class, double dt, double xce[5], double xcr[5]) {

    double xcrref[5], xceref[5], xcrdif[5], xcedif[5]; 
    double epsilon, dtref = 0.0;
    int m;
    logical verified;

    if (*Class != 'S') {
        printf("AUTO2: Invalid workload class %c used for verification.\n", *Class);
        return;
    }

    //---------------------------------------------------------------------
    // tolerance level
    //---------------------------------------------------------------------
    epsilon = 1.0e-08;

    // specify reference values for class S
    dtref = 1.0e-2;

    //---------------------------------------------------------------------
    // Reference values of RMS-norms of residual.
    //---------------------------------------------------------------------
    xcrref[0] = 1.7034283709541311e-01;
    xcrref[1] = 1.2975252070034097e-02;
    xcrref[2] = 3.2527926989486055e-02;
    xcrref[3] = 2.6436421275166801e-02;
    xcrref[4] = 1.9211784131744430e-01;

    //---------------------------------------------------------------------
    // Reference values of RMS-norms of solution error.
    //---------------------------------------------------------------------
    xceref[0] = 4.9976913345811579e-04;
    xceref[1] = 4.5195666782961927e-05;
    xceref[2] = 7.3973765172921357e-05;
    xceref[3] = 7.3821238632439731e-05;
    xceref[4] = 8.9269630987491446e-04;

    //---------------------------------------------------------------------
    // Compute the difference of solution values and the known reference values.
    //---------------------------------------------------------------------
    for (m = 0; m < 5; m++) {
        xcrdif[m] = fabs((xcr[m]-xcrref[m])/xcrref[m]);
        xcedif[m] = fabs((xce[m]-xceref[m])/xceref[m]);
    }

    // ---------------------------------------------------------------------
    // Output the comparison of computed results to known cases.
    // ---------------------------------------------------------------------
    verified = fabs(dt-dtref) <= epsilon;
    if (!verified) {  
        printf("AUTO2 Verification failed.\n");
        return;
    }

    for (m = 0; m < 5; m++) {
        if (xcrdif[m] <= epsilon) {
            verified = true;
        } else { 
            verified = false;
            break;
        }
    }
    if (!verified) {  
        printf("AUTO2 Verification failed.\n");
        return;
    }

    for (m = 0; m < 5; m++) {
        if (xcedif[m] <= epsilon) {
            verified = true;
        } else { 
            verified = false;
            break;
        }
    }
    if (!verified) {  
        printf("AUTO2 Verification failed.\n");
        return;
    }

    printf("AUTO2 Verification successful.\n");
}