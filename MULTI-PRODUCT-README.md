# Multi-Product Support for AWS Marketplace Serverless SaaS Integration

This document outlines the changes made to support multiple products in the AWS Marketplace Serverless SaaS Integration solution.

## Overview

The original solution was designed to work with a single AWS Marketplace product. The updated solution supports multiple products by:

1. Using composite keys in DynamoDB tables
2. Adding Global Secondary Indexes (GSIs) for cross-product queries
3. Updating Lambda functions to handle product-specific data

## Key Changes

### DynamoDB Schema Changes

#### AWSMarketplaceSubscribers Table
- **Primary Key**: Changed from `customerIdentifier` to `productCode#customerIdentifier`
- **Added GSI**: `CustomerIdentifierIndex` on `customerIdentifier` for cross-product queries

#### AWSMarketplaceMeteringRecords Table
- **Primary Key**: Changed from `customerIdentifier` (Hash) and `create_timestamp` (Range) to `productCode#customerIdentifier` (Hash) and `create_timestamp` (Range)
- **Updated GSI**: `PendingMeteringRecordsIndex` now includes `productCode` as a range key
- **Added GSI**: `CustomerIdentifierIndex` on `customerIdentifier` for cross-product queries

### Lambda Function Updates

All Lambda functions have been updated to:
1. Create and use composite keys (`productCode#customerIdentifier`)
2. Include product code in all operations
3. Handle product-specific data in notifications and processing

#### register-new-subscriber.js
- Creates composite key for new subscribers
- Stores product code separately for easier querying

#### entitlement-sqs.js
- Uses composite key for DynamoDB operations
- Processes entitlements per product

#### subscription-sqs.js
- Uses composite key for DynamoDB operations
- Handles subscription events per product

#### metering-hourly-job.js
- Aggregates metering records by product and customer
- Uses composite keys for grouping

#### metering-sqs.js
- Submits metering records to AWS Marketplace with product-specific information
- Updates records using composite keys

#### grant-revoke-access-to-product.js
- Extracts product information from composite keys
- Includes product information in notifications

## Detailed Deployment Steps

### Prerequisites

- AWS CLI installed and configured
- SAM CLI installed
- Node.js 14+ installed
- An AWS account with appropriate permissions
- One or more AWS Marketplace products registered

### Deployment Steps

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/aws-marketplace-serverless-saas-integration.git
   cd aws-marketplace-serverless-saas-integration
   ```

2. **Build the application**:
   ```bash
   sam build
   ```

3. **Deploy the application**:
   ```bash
   sam deploy --guided --capabilities CAPABILITY_NAMED_IAM
   ```

4. **During the guided deployment, provide the following parameters**:
   - **Stack Name**: Name for your CloudFormation stack
   - **AWS Region**: Region to deploy to (default: us-east-1)
   - **WebsiteS3BucketName**: S3 bucket name for the registration website
   - **NewSubscribersTableName**: Name for the subscribers table
   - **AWSMarketplaceMeteringRecordsTableName**: Name for the metering records table
   - **TypeOfSaaSListing**: Type of SaaS listing (contracts_with_subscription, contracts, or subscriptions)
   - **ProductId**: Your AWS Marketplace product ID
   - **MarketplaceTechAdminEmail**: Email to receive notifications
   - **MarketplaceSellerEmail**: Seller email for customer communications
   - **CreateRegistrationWebPage**: Whether to create a registration page (true/false)
   - **UpdateFulfillmentURL**: Whether to automatically update the fulfillment URL in AWS Marketplace (default: false)

5. **After deployment, note the outputs**:
   - **SubscribersTableName**: DynamoDB table for subscribers
   - **MeteringRecordsTableName**: DynamoDB table for metering records
   - **ProductCode**: Product code for your AWS Marketplace product

6. **Complete post-deployment steps**:
   - If you set `UpdateFulfillmentURL` to `false`, manually update the MarketplaceFulfillmentUrl in your AWS Marketplace Management Portal
   - Verify email addresses in Amazon SES
   - Test the registration flow

### Adding Additional Products

The multi-product solution includes a separate template (`add-product-template.yaml`) for adding additional products after the initial deployment. This template creates the necessary SNS subscriptions and optionally creates a new landing page for the new product.

#### Using the Add Product Template

1. **Register the new product in AWS Marketplace** and get its product ID

2. **Get the ARNs of your existing SQS queues**:
   ```bash
   # Get the EntitlementSQSQueue ARN
   ENTITLEMENT_QUEUE_ARN=$(aws cloudformation describe-stacks \
     --stack-name your-main-stack-name \
     --query "Stacks[0].Outputs[?OutputKey=='EntitlementSQSQueueARN'].OutputValue" \
     --output text)
   
   # Get the SubscriptionSQSQueue ARN
   SUBSCRIPTION_QUEUE_ARN=$(aws cloudformation describe-stacks \
     --stack-name your-main-stack-name \
     --query "Stacks[0].Outputs[?OutputKey=='SubscriptionSQSQueueARN'].OutputValue" \
     --output text)
   ```

3. **Deploy the add-product template**:
   ```bash
   sam deploy --guided --template-file add-product-template.yaml
   ```

4. **During the guided deployment, provide the following parameters**:
   - **Stack Name**: Name for your new product stack (e.g., `add-product-xyz`)
   - **NewProductId**: Your new AWS Marketplace product ID
   - **EntitlementSQSQueueARN**: ARN of your existing entitlement SQS queue
   - **SubscriptionSQSQueueARN**: ARN of your existing subscription SQS queue
   - **ExistingFulfillmentURL**: Your existing fulfillment URL (if not creating a new landing page)
   - **ProductType**: Type of SaaS listing for the new product
   - **CreateNewLandingPage**: Whether to create a new landing page for this product
   - **NewLandingPageS3BucketName**: S3 bucket name for the new landing page (if creating one)
   - **UpdateFulfillmentURL**: Whether to automatically update the fulfillment URL in AWS Marketplace

5. **After deployment, note the outputs**:
   - **NewProductCode**: Product code for your new AWS Marketplace product
   - **FulfillmentURL**: The URL that customers will be redirected to after subscribing
   - **NewLandingPageURL**: URL of the new landing page (if created)

The database and Lambda functions will automatically handle the new product's data using the composite keys we've implemented.