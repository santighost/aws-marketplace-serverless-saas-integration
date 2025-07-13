#!/usr/bin/env python3
"""
Utility functions for AWS operations
"""

import boto3
import json

def get_stack_outputs(stack_name):
    """Get the outputs from a CloudFormation stack"""
    cloudformation = boto3.client('cloudformation')
    response = cloudformation.describe_stacks(StackName=stack_name)
    outputs = {output["OutputKey"]: output["OutputValue"] 
               for output in response["Stacks"][0]["Outputs"]}
    return outputs

def get_dynamodb_table(table_name):
    """Get a DynamoDB table resource"""
    dynamodb = boto3.resource('dynamodb')
    return dynamodb.Table(table_name)

def invoke_lambda(function_name, payload):
    """Invoke a Lambda function"""
    lambda_client = boto3.client('lambda')
    response = lambda_client.invoke(
        FunctionName=function_name,
        InvocationType='RequestResponse',
        Payload=json.dumps(payload)
    )
    return json.loads(response['Payload'].read().decode('utf-8'))

def send_sqs_message(queue_url, message_body):
    """Send a message to an SQS queue"""
    sqs = boto3.client('sqs')
    response = sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(message_body)
    )
    return response