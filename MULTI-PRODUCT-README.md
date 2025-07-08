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

For each additional product:

1. **Register the product in AWS Marketplace**

2. **Subscribe the product to the SNS topics**:
   - For entitlements: `aws-mp-entitlement-notification-{ProductCode}`
   - For subscriptions: `aws-mp-subscription-notification-{ProductCode}`

3. **No changes needed to the infrastructure** - the multi-product solution automatically handles multiple products using the composite keys

## Usage

The solution now supports:
- Multiple products using the same infrastructure
- Cross-product customer views using the GSIs
- Product-specific metering and entitlement management

### Querying Across Products

To query all subscriptions for a specific customer across all products:

```javascript
const params = {
  TableName: 'AWSMarketplaceSubscribers',
  IndexName: 'CustomerIdentifierIndex',
  KeyConditionExpression: 'customerIdentifier = :customerId',
  ExpressionAttributeValues: {
    ':customerId': { S: 'customer-123' }
  }
};

const result = await dynamodb.query(params).promise();
```

## Considerations

- **Performance**: Composite keys may impact query performance for very large datasets
- **Scalability**: The solution scales with the number of products and customers
- **Cost**: Additional GSIs may increase DynamoDB costs slightly
- **Migration**: If migrating from the single-product version, use the provided migration script

## Future Enhancements

- Add a product catalog table for product-specific configurations
- Implement a dashboard for cross-product analytics
- Add API endpoints for product management

## Discussion Points

### Multi-Product Support at Deployment Time

Currently, the solution is designed to be deployed with a single product ID, but the database structure supports multiple products. To fully support multiple products at deployment time, we would need to:

1. Change the template to accept a list of product IDs
2. Create multiple SNS subscriptions (one for each product)
3. Configure each Lambda function to handle notifications from all products

For now, the solution supports multiple products through the database structure, but you need to manually subscribe additional products to the SNS topics after deployment.

### Adding a New Product After Initial Deployment

To add support for a new product after the initial deployment, you would need to:

1. **Create the new product in AWS Marketplace** and get its product code

2. **Subscribe the SNS topics to your Lambda functions**:
   - For each new product, you need to manually subscribe your existing Lambda functions to the AWS Marketplace SNS topics for that product
   - Create subscriptions for:
     - Entitlements: `aws-mp-entitlement-notification-{NewProductCode}`
     - Subscriptions: `aws-mp-subscription-notification-{NewProductCode}`

3. **Update the fulfillment URL** in the AWS Marketplace Management Portal for the new product to point to your existing registration endpoint

You don't need to modify the database or Lambda functions since they're already designed to handle multiple products using the composite key structure.

To create the SNS subscriptions manually, you can use the AWS CLI or Console:

```bash
# For entitlements (SaaS Contracts)
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:287250355862:aws-mp-entitlement-notification-{NewProductCode} \
  --protocol sqs \
  --notification-endpoint {YourEntitlementSQSQueueArn}

# For subscriptions (SaaS Subscriptions)
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:287250355862:aws-mp-subscription-notification-{NewProductCode} \
  --protocol sqs \
  --notification-endpoint {YourSubscriptionSQSQueueArn}
```

Replace `{NewProductCode}` with your new product's code and `{YourSQSQueueArn}` with the ARN of your existing SQS queues.

The database and Lambda functions will automatically handle the new product's data using the composite keys we've implemented.

### Suggested Documentation Changes

1. **Update Post-Deployment Steps**:
   - The current documentation mentions manually updating the MarketplaceFulfillmentUrl in the AWS Marketplace Management Portal as a post-deployment step
   - This step is now optional if you set the `UpdateFulfillmentURL` parameter to `true` during deployment
   - The template includes a custom resource that automatically updates the fulfillment URL using the AWS Marketplace Catalog API
   - Documentation should be updated to reflect this automation option

2. **Clarify UpdateFulfillmentURL Parameter**:
   - Add more details about the `UpdateFulfillmentURL` parameter in the deployment parameters section
   - Explain that it's set to `false` by default as a safety measure for existing products
   - Recommend setting it to `true` for new products or development environments to streamline setup

### Automatic Fulfillment URL Update

The multi-product solution includes a feature to automatically update the fulfillment URL in AWS Marketplace. This is controlled by the `UpdateFulfillmentURL` parameter:

- When set to `true`, the solution will automatically update the fulfillment URL in AWS Marketplace using the AWS Marketplace Catalog API
- When set to `false` (default), you'll need to manually update the fulfillment URL in the AWS Marketplace Management Portal

This feature is particularly useful for new products or development environments where you want to streamline the setup process. For existing products that are already published, it's recommended to keep this parameter set to `false` to avoid unintended changes to your product configuration.

## Registration Page Content

The multi-product solution includes automatic deployment of the registration page content to the S3 bucket when `CreateRegistrationWebPage` is set to `true`. The following files are automatically created:

- **index.html**: The main registration page with a form to collect customer information
- **script.js**: JavaScript code to handle form submission and token validation
- **style.css**: CSS styling for the registration page
- **logo.png**: Default logo image
- **favicon.ico**: Browser favicon

These files are created using CloudFormation custom resources that write the content directly to the S3 bucket during deployment. After deployment, you can customize these files by uploading your own versions to the S3 bucket.

### Customizing the Registration Page

To customize the registration page after deployment:

1. Navigate to the S3 bucket created during deployment (available in the CloudFormation outputs)
2. Upload your custom versions of the files (index.html, script.js, style.css, logo.png, favicon.ico)
3. Make sure to maintain the same file structure and form field names in the HTML form
4. Update the script.js file to point to the correct API endpoint if you've modified the API structure

The registration page is designed to collect the following information from customers:
- Company name
- Contact person name
- Contact phone number
- Contact email address

This information is stored in the DynamoDB table along with the AWS Marketplace customer identifier and product code.tup

3. **Add Multi-Product Fulfillment URL Considerations**:
   - When adding additional products, explain that each product needs its fulfillment URL updated
   - Since the `UpdateFulfillmentURL` parameter only works for the initial product, document how to update fulfillment URLs for additional products
   - Consider adding a script or CloudFormation custom resource to automate this process for multiple products