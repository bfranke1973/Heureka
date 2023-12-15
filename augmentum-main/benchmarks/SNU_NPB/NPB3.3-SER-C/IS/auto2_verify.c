#include <stdio.h>
#include <math.h>

// Taken from is.c for Class S
#define  TOTAL_KEYS_LOG_2    16
#define  TEST_ARRAY_SIZE     5
#define  TOTAL_KEYS          (1 << TOTAL_KEYS_LOG_2)
#define  NUM_KEYS            TOTAL_KEYS

typedef  int  INT_TYPE;

// for Class S
INT_TYPE test_index_array[TEST_ARRAY_SIZE]  = 
                             {48427,17148,23627,62548,4431},
         test_rank_array[TEST_ARRAY_SIZE] = 
                             {0,18,346,64917,65463};

// Auto2 verification
// this will not be touched by any optimisations done by auto2 to keep verification and
// benchmark separated
//
// it is only inteded to work for input class S

void auto2_partial_verify(
    char Class, 
    int iteration, 
    INT_TYPE *key_buff_ptr,
    INT_TYPE *partial_verify_vals) 
{

    INT_TYPE    i, k;
    int passed_verification = 0;


    if (Class != 'S') {
        printf("AUTO2: Invalid workload class %c used for verification.\n", Class);
        return;
    }

    printf("AUTO2 Data dump: ");
    for( i=0; i<TEST_ARRAY_SIZE; i++ )
    {
        k = partial_verify_vals[i];          /* test vals were put here */
        printf("%d ", k);
        if( 0 < k  &&  k <= NUM_KEYS-1 )
        {
            INT_TYPE key_rank = key_buff_ptr[k-1];
            int failed = 0;


            if( i <= 2 )
            {
                if( key_rank != test_rank_array[i]+iteration )
                    failed = 1;
                else
                    passed_verification++;
            }
            else
            {
                if( key_rank != test_rank_array[i]-iteration )
                    failed = 1;
                else
                    passed_verification++;
            }
        }
    }
    printf("\n");


    if( passed_verification != 5 /* TEST_ARRAY_SIZE? */ ) {
        printf("AUTO2 Partial verification failed.\n");
    }
}

void auto2_full_verify(INT_TYPE* key_array) {
    INT_TYPE    i, j;

    j = 0;
    for( i=1; i<NUM_KEYS; i++ ) {
        if( key_array[i-1] > key_array[i] ) {
            j++;
        }
    }

    if( j != 0 ) {
        printf("AUTO2 Verification failed.\n");
    } else {
        printf("AUTO2 Verification successful.\n");
    }
}
