# AWS Marketplace Serverless SaaS Integration Test Framework

This directory contains a test framework for the AWS Marketplace Serverless SaaS Integration solution.

## Setup

It's recommended to use a virtual environment to isolate dependencies:

```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install the required Python packages
pip install -r requirements.txt
```

When you're done, you can deactivate the virtual environment:

```bash
deactivate
```

## Running Tests

The main script is `run_tests.py`, which can be used to deploy stacks and run tests.

### Basic Usage

Make sure your virtual environment is activated, then run. The script will prompt you for any required parameters:

```bash
# Deploy the stack without running tests
python run_tests.py --config contracts_with_subscription

# Deploy the stack and run all tests for the configuration
python run_tests.py --config contracts_with_subscription --tests all

# Deploy the stack and run only the registration test
python run_tests.py --config contracts --tests registration

# Test registration with a real AWS Marketplace token
python run_tests.py --config contracts_with_subscription --tests registration --marketplace-token "your-token-here"

# Test with debug output enabled
python run_tests.py --config contracts_with_subscription --tests registration --marketplace-token "your-token-here" --debug

# Test with custom email and product code
python run_tests.py --config contracts_with_subscription --tests registration --marketplace-token "your-token-here" --email "customer@example.com" --product-code "your-product-code"

# Skip deployment and run tests on existing stack
python run_tests.py --skip-deploy --config contracts_with_subscription --tests registration

# Clean up resources after tests
python run_tests.py --config subscriptions --cleanup
```

### Running from Outside the Test Directory

You can also run the script from the project root directory by specifying the path to the config directory:

```bash
# From the project root
python test/run_tests.py --config contracts_with_subscription --config-dir test/config
```

### Command Line Arguments

- `--config`: Test configuration to use (contracts, subscriptions, contracts_with_subscription)
- `--skip-deploy`: Skip deployment and use existing stack
- `--tests`: Specific tests to run. If not specified, only deployment will be performed. Use 'all' to run all tests for the config.
- `--cleanup`: Clean up resources after tests
- `--config-dir`: Directory containing the SAM config files (default: test/config)
- `--marketplace-token`: AWS Marketplace registration token for testing real registration
- `--debug`: Enable detailed debug output for API calls and responses
- `--email`: Email to use for registration (if not provided, you'll be prompted)
- `--product-code`: Product code to use (overrides the one from stack outputs)

### Interactive Prompting

The script will prompt you for parameters in two stages:

1. **Deployment Parameters** (when not using `--skip-deploy`):
   - Seller email (MarketplaceSellerEmail)
   - Tech admin email (MarketplaceTechAdminEmail)
   - Product ID (ProductId) - This is the AWS Marketplace listing ID (e.g., prod-vc7pjbuqesi2q)

2. **Test-Specific Parameters** (when running tests):
   - For registration test:
     - Customer email (used for registration)
     - AWS Marketplace token (optional, for testing real registration)
     - Product code (defaults to the one from stack outputs)

### Product ID vs Product Code

It's important to understand the difference between Product ID and Product Code:

- **Product ID** (e.g., `prod-vc7pjbuqesi2q`):
  - Used for AWS Marketplace listing management
  - Used in SAM deployment as the `ProductId` parameter
  - Format typically starts with `prod-`

- **Product Code** (e.g., `aqofzdc9lpybyqjl1ys98gw1g`):
  - Returned by the `resolveCustomer` API when a customer subscribes
  - Used in DynamoDB composite keys: `productCode#customerIdentifier`
  - Used in AWS Marketplace API calls

When testing with a real token, the Product Code from the `resolveCustomer` API response will be used, regardless of what you specify in the test parameters.

## Adding New Tests

To add a new test:

1. Create a new file in the `test_cases` directory, e.g., `test_new_feature.py`
2. Implement a `run_test(stack_outputs)` function that returns True (pass), False (fail), or None (not implemented)
3. Add the test to the appropriate configuration in `run_tests.py`

## Directory Structure

- `config/`: SAM configuration files for different test scenarios
- `test_cases/`: Individual test modules
- `utils/`: Utility functions
- `run_tests.py`: Main test runner script
- `requirements.txt`: Python package dependencies
- `venv/`: Virtual environment (created during setup)

### Testing with a Real AWS Marketplace Token

You can test the registration flow with a real AWS Marketplace token. This token is provided when a customer subscribes to your product.

To test with a real token:

```bash
# Using the main test runner
python run_tests.py --skip-deploy --config contracts_with_subscription --tests registration --marketplace-token "your-token-here"

# Or run the registration test directly
python test_cases/test_registration.py --token "your-token-here" --stack-name mp-saas-test-contracts-with-subscription
```

The test will:
1. Call the registration API with the token
2. Submit customer information
3. Verify that a customer record is created in DynamoDB with the multi-product format (using composite key)

## Customizing Tests

If you need to modify the test configurations:

1. Edit the appropriate file in the `config/` directory:
   - `samconfig.contracts.toml` - For SaaS contracts only
   - `samconfig.subscriptions.toml` - For SaaS subscriptions only
   - `samconfig.contracts_with_subscription.toml` - For contracts with subscription model

2. Update the stack name, S3 bucket name, and other parameters as needed