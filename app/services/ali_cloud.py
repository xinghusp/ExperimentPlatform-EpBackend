from typing import Dict, Any, List, Optional
import json
import datetime
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.acs_exception.exceptions import ClientException, ServerException
from aliyunsdkecs.request.v20140526.RunInstancesRequest import RunInstancesRequest
from aliyunsdkecs.request.v20140526.DescribeInstanceStatusRequest import DescribeInstanceStatusRequest
from aliyunsdkecs.request.v20140526.DeleteInstanceRequest import DeleteInstanceRequest
from aliyunsdkecs.request.v20140526.DescribeInstancesRequest import DescribeInstancesRequest

from app.core.config import settings


class AliCloudService:
    def __init__(self):
        self.client = AcsClient(
            settings.ALIYUN_ACCESS_KEY_ID,
            settings.ALIYUN_ACCESS_KEY_SECRET
        )
    
    def create_ecs_instance(
        self,
        region_id: str,
        image_id: str,
        instance_type: str,
        security_group_id: str,
        vswitch_id: str,
        internet_max_bandwidth_out: int,
        spot_strategy: str,
        password: str,
        auto_release_time: Optional[datetime.datetime] = None,
        custom_params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        request = RunInstancesRequest()
        request.set_accept_format('json')
        
        # 必须参数
        request.set_ImageId(image_id)
        request.set_InstanceType(instance_type)
        request.set_SecurityGroupId(security_group_id)
        request.set_VSwitchId(vswitch_id)
        request.set_InternetMaxBandwidthOut(internet_max_bandwidth_out)
        request.set_SpotStrategy(spot_strategy)
        request.set_Password(password)
        
        # 可选参数 - 实例自动释放时间
        if auto_release_time:
            # 转换为阿里云所需格式: 2025-03-07T08:44:52Z
            formatted_time = auto_release_time.strftime('%Y-%m-%dT%H:%M:%SZ')
            request.set_AutoReleaseTime(formatted_time)
        
        # 自定义参数
        if custom_params:
            for key, value in custom_params.items():
                method_name = f"set_{key}"
                if hasattr(request, method_name):
                    method = getattr(request, method_name)
                    method(value)
        
        try:
            response = self.client.do_action_with_exception(request)
            result = json.loads(response)
            return {"success": True, "instance_ids": result.get("InstanceIdSets", {}).get("InstanceIdSet", [])}
        except (ServerException, ClientException) as e:
            return {"success": False, "error": str(e)}

    def describe_instance_status(self, instance_ids: List[str]) -> Dict[str, Any]:
        request = DescribeInstanceStatusRequest()
        request.set_accept_format('json')

        request.set_InstanceIds(instance_ids)
        
        try:
            response = self.client.do_action_with_exception(request)
            result = json.loads(response)
            return {
                "success": True, 
                "instances": result.get("InstanceStatuses", {}).get("InstanceStatus", [])
            }
        except (ServerException, ClientException) as e:
            return {"success": False, "error": str(e)}

    def describe_instance(self, instance_ids: List[str]) -> Dict[str, Any]:
        request = DescribeInstancesRequest()
        request.set_accept_format('json')
        request.set_InstanceIds(instance_ids)

        try:
            response = self.client.do_action_with_exception(request)
            result = json.loads(response)
            return {
                "success": True,
                "instances": result.get("Instances", {}).get("Instance", [])
            }
        except (ServerException, ClientException) as e:
            return {"success": False, "error": str(e)}
    
    def delete_instance(self, region_id: str, instance_id: str, force: bool = True) -> Dict[str, Any]:
        request = DeleteInstanceRequest()
        request.set_accept_format('json')
        request.set_InstanceId(instance_id)
        request.set_Force(force)
        
        try:
            response = self.client.do_action_with_exception(request)
            result = json.loads(response)
            return {"success": True, "result": result}
        except (ServerException, ClientException) as e:
            return {"success": False, "error": str(e)}


ali_cloud_service = AliCloudService()