# AWS Marketplace SaaS Integration Tests

This directory contains tests for the AWS Marketplace Serverless SaaS Integration. The tests are designed to verify the functionality of the integration with AWS Marketplace.

## Test Framework

The test framework is built using Python and provides a way to test the various components of the AWS Marketplace SaaS Integration:

- **Registration**: Tests the customer registration flow
- **Entitlement**: Tests the entitlement flow for contract-based products
- **Subscription**: Tests the subscription flow for subscription-based products
- **Metering**: Tests the metering flow for usage-based billing
- **Grant/Revoke Access**: Tests the ability to grant and revoke access to customers

## Running Tests

To run the tests, use the `run_tests.py` script:

```bash
python run_tests.py [options]
```

### Options

- `--config`: Choose the configuration to test (contracts, subscriptions, contracts_with_subscription)
- `--skip-deploy`: Skip deployment and use an existing stack
- `--tests`: Specify which tests to run (e.g., registration, entitlement, subscription, metering, grant_revoke)
- `--cleanup`: Clean up resources after tests
- `--debug`: Enable debug output
- `--email`: Email to use for registration
- `--product-code`: Product code to use (overrides the one from stack outputs)
- `--customer-id`: Customer identifier to use for testing (if not provided, a new test customer will be created)
- `--marketplace-token`: AWS Marketplace registration token for testing real registration

### Examples

Deploy and run all tests for the contracts_with_subscription configuration:
```bash
python run_tests.py --config contracts_with_subscription --tests all
```

Run only the entitlement test on an existing stack:
```bash
python run_tests.py --skip-deploy --config contracts_with_subscription --tests entitlement
```

Run the metering test with a specific customer ID:
```bash
python run_tests.py --skip-deploy --config contracts_with_subscription --tests metering --customer-id YOUR_CUSTOMER_ID
```

## Test Cases

### Registration Test

Tests the customer registration flow:
- Creates a new customer record in DynamoDB
- Verifies that the customer record was created correctly

### Entitlement Test

Tests the entitlement flow for contract-based products:
- Creates a new customer record or uses an existing one
- Sends an entitlement notification to the SQS queue (for real customers)
- Simulates an entitlement update (for test customers)
- Verifies that the customer record was updated with entitlement information

### Subscription Test

Tests the subscription flow for subscription-based products:
- Creates a new customer record or uses an existing one
- Sends a subscription notification to the SQS queue (for real customers)
- Simulates a subscription update (for test customers)
- Verifies that the customer record was updated with subscription information

### Metering Test

Tests the metering flow for usage-based billing:
- Creates a new customer record or uses an existing one
- Creates a metering record in the metering records table
- For real customers, tries to get dimensions from existing entitlements
- Invokes the metering hourly job Lambda function
- Verifies that the metering record was processed

### Grant/Revoke Access Test

Tests the ability to grant and revoke access to customers:
- Creates a new customer record or uses an existing one
- Tests granting access by setting `successfully_subscribed` to `true` and `subscription_expired` to `false`
- Verifies that access was granted
- Tests revoking access by setting `subscription_expired` to `true`
- Verifies that access was revoked
- For real customers, restores the original state

## Testing with Real Customers

When testing with real customers (by providing a `--customer-id`), the tests will:
1. Use the existing customer record from DynamoDB
2. Use real SQS queues and Lambda functions
3. For metering, try to get dimensions from existing entitlements
4. For grant/revoke access, restore the original state after the test

## Testing with Test Customers

When testing with test customers (no `--customer-id` provided), the tests will:
1. Create a new test customer with a random ID
2. Use simulated updates for entitlements and subscriptions
3. Use default test dimensions for metering
4. Not restore the original state after grant/revoke access tests

## Configuration

The test framework supports three configurations:

1. **contracts**: For testing contract-based products
2. **subscriptions**: For testing subscription-based products
3. **contracts_with_subscription**: For testing products with both contracts and subscriptions

Each configuration has its own SAM template and set of tests.