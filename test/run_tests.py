#!/usr/bin/env python3
"""
Master test script for AWS Marketplace Serverless SaaS Integration
"""

import argparse
import os
import subprocess
import sys
import time
import json
import boto3
import importlib.util
import inspect
from utils import prompt_utils

# Configuration
TEST_CONFIGS = {
    "contracts": {
        "config_file": "config/samconfig.contracts.toml",
        "stack_name": "mp-saas-test-contracts",
        "tests": ["registration", "entitlement", "grant_revoke"]
    },
    "subscriptions": {
        "config_file": "config/samconfig.subscriptions.toml",
        "stack_name": "mp-saas-test-subscriptions",
        "tests": ["registration", "subscription", "metering"]
    },
    "contracts_with_subscription": {
        "config_file": "config/samconfig.contracts_with_subscription.toml",
        "stack_name": "mp-saas-test-contracts-with-subscription",
        "tests": ["registration", "entitlement", "subscription", "metering", "grant_revoke", "multi_product"]
    }
}

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Run tests for AWS Marketplace Serverless SaaS Integration")
    parser.add_argument("--config", choices=TEST_CONFIGS.keys(), default="contracts_with_subscription",
                        help="Test configuration to use")
    parser.add_argument("--skip-deploy", action="store_true", 
                        help="Skip deployment and use existing stack")
    parser.add_argument("--tests", nargs="+", 
                        help="Specific tests to run. If not specified, only deployment will be performed. Use 'all' to run all tests for the config.")
    # Removed --comprehensive flag as it's now automatically enabled with --tests all
    parser.add_argument("--cleanup", action="store_true",
                        help="Clean up resources after tests")
    parser.add_argument("--config-dir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "config"),
                        help="Directory containing the SAM config files")
    parser.add_argument("--marketplace-token", 
                        help="AWS Marketplace registration token for testing real registration")
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug output")
    parser.add_argument("--email", 
                        help="Email to use for registration")
    parser.add_argument("--product-code", 
                        help="Product code to use (overrides the one from stack outputs)")
    parser.add_argument("--customer-id", 
                        help="Customer identifier to use for testing (if not provided, a new test customer will be created)")
    parser.add_argument("--second-product-code", 
                        help="Secondary product code for multi-product testing")
    return parser.parse_args()

def load_test_module(test_name):
    """Dynamically load a test module"""
    try:
        module_path = os.path.join(os.path.dirname(__file__), 'test_cases', f'test_{test_name}.py')
        spec = importlib.util.spec_from_file_location(f"test_{test_name}", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        print(f"ERROR: Failed to load test module {test_name}: {e}")
        return None

def deploy_stack(config_name, config_dir):
    """Deploy CloudFormation stack using the specified config"""
    config = TEST_CONFIGS[config_name]
    
    # Build the full path to the config file
    config_file = os.path.join(config_dir, os.path.basename(config["config_file"]))
    
    # Prompt for deployment parameters
    print(f"\nPreparing to deploy stack {config['stack_name']} using {config_file}...")
    
    # Load and print current config parameters
    params = prompt_utils.load_config_parameters(config_file)
    print("\nCurrent config values:")
    for key, value in params.items():
        print(f"  {key}: {value}")
    print()
    
    # Ask if the user wants to change any parameters
    change_params = input("Do you want to change any deployment parameters? [y/N]: ").lower() == 'y'
    
    if change_params:
        # We already printed the current values in prompt_utils.prompt_for_deployment_parameters
        params = prompt_utils.prompt_for_deployment_parameters(config_name, config_dir)
        
        # Print the parameters that will be used
        print("\nDeploying with the following parameters:")
        for key, value in params.items():
            print(f"  {key}: {value}")
        
        # Confirm deployment
        if input("\nProceed with deployment? [Y/n]: ").lower() not in ['', 'y', 'yes']:
            print("Deployment cancelled.")
            return None
        
        # Build parameter overrides string - exclude region as it's a separate parameter
        param_overrides = [f"{key}=\"{value}\"" for key, value in params.items() if key != "region"]
        param_overrides_str = " ".join(param_overrides)
    else:
        param_overrides_str = ""
    
    print(f"\nDeploying stack {config['stack_name']}...")
    
    # Copy the config file to the root directory
    subprocess.run(["cp", config_file, "../samconfig.toml"], check=True)
    
    # Change to the parent directory where the template.yaml is located
    current_dir = os.getcwd()
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    try:
        # Build and deploy
        subprocess.run(["sam", "build"], check=True)
        
        deploy_cmd = ["sam", "deploy", "--no-confirm-changeset", "--capabilities", "CAPABILITY_NAMED_IAM"]
        if "region" in params:
            deploy_cmd.extend(["--region", params["region"]])
        if param_overrides_str:
            deploy_cmd.extend(["--parameter-overrides", param_overrides_str])
        
        subprocess.run(deploy_cmd, check=True)
    finally:
        # Change back to the original directory
        os.chdir(current_dir)
    
    # Get stack outputs
    cloudformation = boto3.client('cloudformation')
    response = cloudformation.describe_stacks(StackName=config["stack_name"])
    outputs = {output["OutputKey"]: output["OutputValue"] 
               for output in response["Stacks"][0]["Outputs"]}
    
    # Print stack outputs
    print("\nStack outputs:")
    for key, value in outputs.items():
        print(f"  {key}: {value}")
    
    return outputs

def run_tests(config_name, stack_outputs, selected_tests=None, marketplace_token=None, debug=False, email=None, product_code=None, customer_id=None, chained_mode=False):
    """Run the specified tests
    
    Args:
        config_name: Name of the configuration to test
        stack_outputs: CloudFormation stack outputs
        selected_tests: List of tests to run (None for all tests)
        marketplace_token: AWS Marketplace registration token
        debug: Enable debug output
        email: Email to use for registration
        product_code: Product code to use
        customer_id: Customer identifier to use
        chained_mode: Run tests in a chained flow, passing data between tests
    """
    config = TEST_CONFIGS[config_name]
    tests_to_run = selected_tests if selected_tests else config["tests"]
    
    results = {}
    registered_customer_id = None
    
    # For chained mode testing, ensure registration is first
    if chained_mode and "registration" in tests_to_run and tests_to_run[0] != "registration":
        tests_to_run.remove("registration")
        tests_to_run.insert(0, "registration")
    
    for test in tests_to_run:
        print(f"\nRunning test: {test}")
        test_module = load_test_module(test)
        
        if test_module and hasattr(test_module, 'run_test'):
            try:
                # For chained mode testing, use the customer ID and product code from registration
                if chained_mode and test != "registration" and registered_customer_id:
                    customer_id = registered_customer_id
                    print(f"Using customer ID from registration: {customer_id}")
                
                # Pass marketplace_token to registration test
                if test == "registration":
                    # If chained mode testing and no token provided, prompt for one
                    if chained_mode and not marketplace_token:
                        marketplace_token = input("Enter AWS Marketplace registration token (leave empty for simulated test): ")
                    
                    # Run the registration test
                    if marketplace_token:
                        results[test] = test_module.run_test(stack_outputs, marketplace_token, debug, config_name, email, product_code)
                    else:
                        results[test] = test_module.run_test(stack_outputs, debug=debug, config_name=config_name, registration_email=email, override_product_code=product_code)
                    
                    # For chained mode testing, extract the customer ID from the result
                    if chained_mode and results[test] and hasattr(test_module, 'get_customer_id'):
                        registered_customer_id = test_module.get_customer_id()
                        print(f"Extracted customer ID from registration: {registered_customer_id}")
                elif test == "multi_product":
                    # Pass second_product_code to multi_product test
                    second_product_code = getattr(args, 'second_product_code', None)
                    results[test] = test_module.run_test(stack_outputs, debug=debug, config_name=config_name, registration_email=email, override_product_code=product_code, customer_id=customer_id, second_product_code=second_product_code)
                else:
                    results[test] = test_module.run_test(stack_outputs, debug=debug, config_name=config_name, registration_email=email, override_product_code=product_code, customer_id=customer_id)
            except Exception as e:
                print(f"ERROR: Test {test} failed with exception: {e}")
                results[test] = False
                
                # For chained mode testing, stop if a test fails
                if chained_mode:
                    print("Stopping chained testing due to test failure")
                    break
        else:
            print(f"Test '{test}' not implemented yet")
            results[test] = None
    
    # Print a summary of the test results
    print("\n=== Test Results Summary ===")
    for test, result in results.items():
        status = "PASS" if result else "NOT IMPLEMENTED" if result is None else "FAIL"
        print(f"{test}: {status}")
    
    # Calculate overall pass rate
    total_tests = len(results)
    passed_tests = sum(1 for result in results.values() if result)
    not_implemented = sum(1 for result in results.values() if result is None)
    failed_tests = total_tests - passed_tests - not_implemented
    
    if total_tests > 0:
        pass_rate = (passed_tests / (total_tests - not_implemented)) * 100 if (total_tests - not_implemented) > 0 else 0
        print(f"\nPass rate: {pass_rate:.1f}% ({passed_tests}/{total_tests - not_implemented})")
        print(f"Tests passed: {passed_tests}")
        print(f"Tests failed: {failed_tests}")
        if not_implemented > 0:
            print(f"Tests not implemented: {not_implemented}")
    
    return results

def cleanup_resources(config_name):
    """Clean up deployed resources"""
    config = TEST_CONFIGS[config_name]
    
    print(f"\nCleaning up stack {config['stack_name']}...")
    subprocess.run(["sam", "delete", "--stack-name", config["stack_name"], "--no-prompts"], check=True)

def main():
    """Main function"""
    args = parse_args()
    
    try:
        if args.skip_deploy:
            print(f"Skipping deployment, using existing {args.config} stack...")
            # Get stack outputs
            cloudformation = boto3.client('cloudformation')
            response = cloudformation.describe_stacks(StackName=TEST_CONFIGS[args.config]["stack_name"])
            stack_outputs = {output["OutputKey"]: output["OutputValue"] 
                           for output in response["Stacks"][0]["Outputs"]}
            
            # Print stack outputs
            print("\nStack outputs:")
            for key, value in stack_outputs.items():
                print(f"  {key}: {value}")
        else:
            stack_outputs = deploy_stack(args.config, args.config_dir)
            print(f"Stack {TEST_CONFIGS[args.config]['stack_name']} deployed successfully")
        
        # Run tests if --tests is specified
        if args.tests:
            # Handle 'all' as a special case
            if 'all' in args.tests:
                tests_to_run = None  # This will use all tests for the config
            else:
                tests_to_run = args.tests
            
            # If running all tests, automatically enable chained mode
            chained_mode = (tests_to_run is None)
            
            # Prompt for test-specific parameters
            test_params = {}
            for test in tests_to_run if tests_to_run else TEST_CONFIGS[args.config]["tests"]:
                test_params[test] = prompt_utils.prompt_for_test_parameters(test, args.config, args.config_dir, stack_outputs, args.marketplace_token, chained_mode)
                
            # Override command line arguments with prompted values
            if "registration" in test_params and test_params["registration"]:
                if test_params["registration"].get("email") and not args.email:
                    args.email = test_params["registration"]["email"]
                if test_params["registration"].get("product_code") and not args.product_code:
                    args.product_code = test_params["registration"]["product_code"]
                if test_params["registration"].get("marketplace_token") and not args.marketplace_token:
                    args.marketplace_token = test_params["registration"]["marketplace_token"]
            
            # Override customer_id for all tests that need it
            for test_type in ["entitlement", "subscription", "metering", "grant_revoke", "multi_product"]:
                if test_type in test_params and test_params[test_type]:
                    if test_params[test_type].get("customer_id") and not args.customer_id:
                        args.customer_id = test_params[test_type]["customer_id"]
                    if test_params[test_type].get("product_code") and not args.product_code:
                        args.product_code = test_params[test_type]["product_code"]
                    if test_type == "multi_product" and test_params[test_type].get("second_product_code") and not args.second_product_code:
                        args.second_product_code = test_params[test_type]["second_product_code"]
            
            # Run tests
            test_results = run_tests(args.config, stack_outputs, tests_to_run, args.marketplace_token, args.debug, args.email, args.product_code, args.customer_id, chained_mode)
            
            # Print results
            print("\n=== Test Results ===")
            for test, result in test_results.items():
                status = "PASS" if result else "NOT IMPLEMENTED" if result is None else "FAIL"
                print(f"{test}: {status}")
        else:
            print("\nNo tests specified. Use --tests option to run tests.")
        
        # Clean up if requested
        if args.cleanup:
            cleanup_resources(args.config)
        
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()