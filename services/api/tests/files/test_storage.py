from pathlib import Path

import boto3
import pytest
from botocore.response import StreamingBody
from botocore.stub import Stubber
from io import BytesIO

from src.files.storage import MemoryStorage, S3Storage


def test_s3_adapter_round_trip_and_delete_without_live_service(tmp_path):
    client = boto3.client('s3', region_name='us-east-1', aws_access_key_id='test', aws_secret_access_key='test')
    storage = S3Storage(bucket='sources', client=client)
    path = tmp_path / 'source.csv'
    path.write_bytes(b'a,b\n1,2\n')
    # Real botocore request serialization and response parsing, network stubbed.
    with Stubber(client) as stub:
        from botocore.stub import ANY
        stub.add_response('put_object', {}, {'Bucket': 'sources', 'Key': 'key', 'Body': ANY, 'ContentType': 'text/csv'})
        stub.add_response('get_object', {'Body': StreamingBody(BytesIO(b'a,b\n1,2\n'), 8)}, {'Bucket': 'sources', 'Key': 'key'})
        stub.add_response('delete_object', {}, {'Bucket': 'sources', 'Key': 'key'})
        storage.put_file('key', path, 'text/csv')
        storage.download_file('key', tmp_path / 'copy.csv', max_bytes=100)
        assert (tmp_path / 'copy.csv').read_bytes() == b'a,b\n1,2\n'
        storage.delete('key')
        stub.assert_no_pending_responses()


def test_storage_download_cannot_exceed_limit(tmp_path):
    storage = MemoryStorage()
    storage.objects['key'] = b'12345'
    with pytest.raises(ValueError):
        storage.download_file('key', tmp_path / 'copy', max_bytes=4)
