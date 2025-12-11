"""
Monitoring and logging functionality for AphexPipeline.

This module provides workflow metadata recording, CloudWatch metrics emission,
and notification delivery capabilities.
"""

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any
import boto3
from botocore.exceptions import ClientError


@dataclass
class StageMetadata:
    """Metadata for a single workflow stage."""
    stage_name: str
    started_at: str  # ISO format datetime string
    completed_at: Optional[str] = None  # ISO format datetime string
    status: str = "running"  # "running", "succeeded", "failed"
    error_message: Optional[str] = None


@dataclass
class WorkflowMetadata:
    """Metadata for a workflow execution."""
    workflow_id: str
    commit_sha: str
    branch: str
    triggered_at: str  # ISO format datetime string
    completed_at: Optional[str] = None  # ISO format datetime string
    status: str = "running"  # "running", "succeeded", "failed"
    stages: List[StageMetadata] = None
    
    def __post_init__(self):
        if self.stages is None:
            self.stages = []


class WorkflowMetadataRecorder:
    """Records workflow metadata to S3 for auditing and monitoring."""
    
    def __init__(self, bucket_name: Optional[str] = None, s3_client=None):
        """
        Initialize the metadata recorder.
        
        Args:
            bucket_name: S3 bucket name for storing metadata. If None, uses ARTIFACT_BUCKET env var.
            s3_client: Optional boto3 S3 client for testing. If None, creates a new client.
        """
        self.bucket_name = bucket_name or os.environ.get('ARTIFACT_BUCKET')
        if not self.bucket_name:
            raise ValueError("bucket_name must be provided or ARTIFACT_BUCKET environment variable must be set")
        
        self.s3_client = s3_client or boto3.client('s3')
    
    def record_workflow_metadata(self, metadata: WorkflowMetadata) -> str:
        """
        Record workflow metadata to S3.
        
        Args:
            metadata: WorkflowMetadata object to record
            
        Returns:
            S3 path where metadata was stored
            
        Raises:
            ClientError: If S3 upload fails
        """
        # Create S3 key with workflow ID and timestamp
        s3_key = f"metadata/workflows/{metadata.workflow_id}.json"
        
        # Convert metadata to JSON
        metadata_dict = asdict(metadata)
        metadata_json = json.dumps(metadata_dict, indent=2)
        
        # Upload to S3
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=metadata_json.encode('utf-8'),
                ContentType='application/json'
            )
        except ClientError as e:
            raise ClientError(
                error_response=e.response,
                operation_name='PutObject'
            ) from e
        
        return f"s3://{self.bucket_name}/{s3_key}"
    
    def retrieve_workflow_metadata(self, workflow_id: str) -> WorkflowMetadata:
        """
        Retrieve workflow metadata from S3.
        
        Args:
            workflow_id: Workflow ID to retrieve
            
        Returns:
            WorkflowMetadata object
            
        Raises:
            ClientError: If S3 download fails or workflow not found
        """
        s3_key = f"metadata/workflows/{workflow_id}.json"
        
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            metadata_json = response['Body'].read().decode('utf-8')
            metadata_dict = json.loads(metadata_json)
            
            # Reconstruct StageMetadata objects
            stages = [StageMetadata(**stage) for stage in metadata_dict.get('stages', [])]
            metadata_dict['stages'] = stages
            
            return WorkflowMetadata(**metadata_dict)
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                raise ClientError(
                    error_response={'Error': {'Code': 'NoSuchKey', 'Message': f'Workflow {workflow_id} not found'}},
                    operation_name='GetObject'
                ) from e
            raise
    
    def update_workflow_status(self, workflow_id: str, status: str, completed_at: Optional[str] = None) -> None:
        """
        Update the status of an existing workflow.
        
        Args:
            workflow_id: Workflow ID to update
            status: New status ("running", "succeeded", "failed")
            completed_at: Optional completion timestamp in ISO format
        """
        # Retrieve existing metadata
        metadata = self.retrieve_workflow_metadata(workflow_id)
        
        # Update status
        metadata.status = status
        if completed_at:
            metadata.completed_at = completed_at
        
        # Record updated metadata
        self.record_workflow_metadata(metadata)
    
    def add_stage_metadata(self, workflow_id: str, stage: StageMetadata) -> None:
        """
        Add stage metadata to an existing workflow.
        
        Args:
            workflow_id: Workflow ID to update
            stage: StageMetadata to add
        """
        # Retrieve existing metadata
        metadata = self.retrieve_workflow_metadata(workflow_id)
        
        # Add stage
        metadata.stages.append(stage)
        
        # Record updated metadata
        self.record_workflow_metadata(metadata)


class CloudWatchMetricsEmitter:
    """Emits CloudWatch metrics for workflow and deployment events."""
    
    def __init__(self, namespace: str = "AphexPipeline", cloudwatch_client=None):
        """
        Initialize the metrics emitter.
        
        Args:
            namespace: CloudWatch namespace for metrics
            cloudwatch_client: Optional boto3 CloudWatch client for testing
        """
        self.namespace = namespace
        self.cloudwatch_client = cloudwatch_client or boto3.client('cloudwatch')
    
    def emit_deployment_metric(
        self,
        stack_name: str,
        success: bool,
        duration_seconds: Optional[float] = None,
        environment: Optional[str] = None
    ) -> None:
        """
        Emit CloudWatch metric for a CDK stack deployment.
        
        Args:
            stack_name: Name of the CDK stack
            success: Whether deployment succeeded
            duration_seconds: Optional deployment duration in seconds
            environment: Optional environment name
        """
        metric_data = []
        
        # Deployment success/failure metric
        dimensions = [
            {'Name': 'StackName', 'Value': stack_name},
            {'Name': 'Status', 'Value': 'Success' if success else 'Failure'}
        ]
        
        if environment:
            dimensions.append({'Name': 'Environment', 'Value': environment})
        
        metric_data.append({
            'MetricName': 'DeploymentCount',
            'Value': 1.0,
            'Unit': 'Count',
            'Dimensions': dimensions,
            'Timestamp': datetime.utcnow()
        })
        
        # Duration metric if provided
        if duration_seconds is not None:
            metric_data.append({
                'MetricName': 'DeploymentDuration',
                'Value': duration_seconds,
                'Unit': 'Seconds',
                'Dimensions': [d for d in dimensions if d['Name'] != 'Status'],
                'Timestamp': datetime.utcnow()
            })
        
        # Put metrics to CloudWatch
        self.cloudwatch_client.put_metric_data(
            Namespace=self.namespace,
            MetricData=metric_data
        )
    
    def emit_workflow_metric(
        self,
        workflow_id: str,
        status: str,
        duration_seconds: Optional[float] = None
    ) -> None:
        """
        Emit CloudWatch metric for a workflow execution.
        
        Args:
            workflow_id: Workflow ID
            status: Workflow status ("succeeded", "failed")
            duration_seconds: Optional workflow duration in seconds
        """
        metric_data = []
        
        # Workflow completion metric
        dimensions = [
            {'Name': 'Status', 'Value': status}
        ]
        
        metric_data.append({
            'MetricName': 'WorkflowCount',
            'Value': 1.0,
            'Unit': 'Count',
            'Dimensions': dimensions,
            'Timestamp': datetime.utcnow()
        })
        
        # Duration metric if provided
        if duration_seconds is not None:
            metric_data.append({
                'MetricName': 'WorkflowDuration',
                'Value': duration_seconds,
                'Unit': 'Seconds',
                'Dimensions': [],
                'Timestamp': datetime.utcnow()
            })
        
        # Put metrics to CloudWatch
        self.cloudwatch_client.put_metric_data(
            Namespace=self.namespace,
            MetricData=metric_data
        )


class NotificationDelivery:
    """Delivers notifications for workflow events."""
    
    def __init__(self, sns_client=None):
        """
        Initialize the notification delivery.
        
        Args:
            sns_client: Optional boto3 SNS client for testing
        """
        self.sns_client = sns_client or boto3.client('sns')
    
    def send_notification(
        self,
        topic_arn: str,
        workflow_id: str,
        status: str,
        commit_sha: str,
        argo_ui_url: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> str:
        """
        Send notification via SNS.
        
        Args:
            topic_arn: SNS topic ARN
            workflow_id: Workflow ID
            status: Workflow status ("succeeded", "failed")
            commit_sha: Git commit SHA
            argo_ui_url: Optional Argo UI URL for the workflow
            error_message: Optional error message for failed workflows
            
        Returns:
            SNS message ID
        """
        # Build notification message
        subject = f"AphexPipeline Workflow {status.upper()}: {workflow_id}"
        
        message_lines = [
            f"Workflow ID: {workflow_id}",
            f"Status: {status}",
            f"Commit SHA: {commit_sha}",
        ]
        
        if argo_ui_url:
            message_lines.append(f"Argo UI: {argo_ui_url}")
        
        if error_message:
            message_lines.append(f"\nError: {error_message}")
        
        message = "\n".join(message_lines)
        
        # Send notification
        response = self.sns_client.publish(
            TopicArn=topic_arn,
            Subject=subject,
            Message=message
        )
        
        return response['MessageId']
    
    def send_notification_to_multiple_channels(
        self,
        topic_arns: List[str],
        workflow_id: str,
        status: str,
        commit_sha: str,
        argo_ui_url: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> List[str]:
        """
        Send notification to multiple SNS topics (channels).
        
        Args:
            topic_arns: List of SNS topic ARNs
            workflow_id: Workflow ID
            status: Workflow status
            commit_sha: Git commit SHA
            argo_ui_url: Optional Argo UI URL
            error_message: Optional error message
            
        Returns:
            List of SNS message IDs
        """
        message_ids = []
        
        for topic_arn in topic_arns:
            message_id = self.send_notification(
                topic_arn=topic_arn,
                workflow_id=workflow_id,
                status=status,
                commit_sha=commit_sha,
                argo_ui_url=argo_ui_url,
                error_message=error_message
            )
            message_ids.append(message_id)
        
        return message_ids


def create_workflow_metadata(
    workflow_id: str,
    commit_sha: str,
    branch: str,
    triggered_at: Optional[datetime] = None
) -> WorkflowMetadata:
    """
    Create a new WorkflowMetadata object.
    
    Args:
        workflow_id: Workflow ID
        commit_sha: Git commit SHA
        branch: Git branch name
        triggered_at: Optional trigger timestamp (defaults to now)
        
    Returns:
        WorkflowMetadata object
    """
    if triggered_at is None:
        triggered_at = datetime.utcnow()
    
    return WorkflowMetadata(
        workflow_id=workflow_id,
        commit_sha=commit_sha,
        branch=branch,
        triggered_at=triggered_at.isoformat(),
        status="running",
        stages=[]
    )


def create_stage_metadata(
    stage_name: str,
    started_at: Optional[datetime] = None
) -> StageMetadata:
    """
    Create a new StageMetadata object.
    
    Args:
        stage_name: Name of the stage
        started_at: Optional start timestamp (defaults to now)
        
    Returns:
        StageMetadata object
    """
    if started_at is None:
        started_at = datetime.utcnow()
    
    return StageMetadata(
        stage_name=stage_name,
        started_at=started_at.isoformat(),
        status="running"
    )
