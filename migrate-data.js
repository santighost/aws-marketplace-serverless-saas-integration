// This is a template for data migration - DO NOT run without thorough testing
const AWS = require('aws-sdk');
const dynamodb = new AWS.DynamoDB();

async function migrateSubscribers() {
  const oldTableName = 'AWSMakretplaceSubscribers-dniezgod-v1';
  const newTableName = 'AWSMakretplaceSubscribers-multiproduct';
  
  // Scan the old table
  const scanParams = { TableName: oldTableName };
  const scanResult = await dynamodb.scan(scanParams).promise();
  
  // Process each item
  for (const item of scanResult.Items) {
    const customerIdentifier = item.customerIdentifier.S;
    const productCode = item.productCode.S;
    
    // Create composite key
    const compositeKey = `${productCode}#${customerIdentifier}`;
    
    // Create new item with composite key
    const newItem = {...item};
    newItem['productCode#customerIdentifier'] = { S: compositeKey };
    
    // Write to new table
    const putParams = {
      TableName: newTableName,
      Item: newItem
    };
    
    await dynamodb.putItem(putParams).promise();
    console.log(`Migrated subscriber: ${customerIdentifier} for product: ${productCode}`);
  }
}

async function migrateMeteringRecords() {
  const oldTableName = 'AWSMarketplaceMeteringRecords-dniezgod-v1';
  const newTableName = 'AWSMarketplaceMeteringRecords-multiproduct';
  
  // Scan the old table
  const scanParams = { TableName: oldTableName };
  const scanResult = await dynamodb.scan(scanParams).promise();
  
  // Process each item
  for (const item of scanResult.Items) {
    const customerIdentifier = item.customerIdentifier.S;
    const productCode = item.productCode ? item.productCode.S : 'default-product-code';
    const createTimestamp = item.create_timestamp.N;
    
    // Create composite key
    const compositeKey = `${productCode}#${customerIdentifier}`;
    
    // Create new item with composite key
    const newItem = {...item};
    newItem['productCode#customerIdentifier'] = { S: compositeKey };
    
    // Write to new table
    const putParams = {
      TableName: newTableName,
      Item: newItem
    };
    
    await dynamodb.putItem(putParams).promise();
    console.log(`Migrated metering record: ${customerIdentifier}, timestamp: ${createTimestamp}`);
  }
}

// Execute migration
async function migrate() {
  try {
    await migrateSubscribers();
    await migrateMeteringRecords();
    console.log('Migration completed successfully');
  } catch (error) {
    console.error('Migration failed:', error);
  }
}

// Uncomment to run
// migrate();