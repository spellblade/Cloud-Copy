2026-09-07 16:59:18,041 WARNING [app.services.pikpak_client] PikPak S3 upload attempt 1/3 failed (SSLError); retrying in 2s
2026-09-07 17:01:50,045 WARNING [app.services.pikpak_client] PikPak S3 upload attempt 2/3 failed (SSLError); retrying in 4s
2026-09-07 17:04:18,501 INFO [httpx] HTTP Request: POST https://api-drive.mypikpak.com/drive/v1/files:batchDelete "HTTP/1.1 200 OK"
2026-09-07 17:04:18,617 INFO [httpx] HTTP Request: DELETE https://api-drive.mypikpak.com/drive/v1/tasks?task_ids=VP0vbjW9UMNVNOPaMY60Z7cgo2&delete_files=false "HTTP/1.1 200 OK"
2026-09-07 17:04:18,821 ERROR [app.services.transfer_service] Job 6c79dd31-2598-45a3-8e97-55bee144f515 failed
Traceback (most recent call last):
  File "/home/soham/projects/Cloud-Copy/.venv/lib/python3.12/site-packages/urllib3/connectionpool.py", line 788, in urlopen
    response = self._make_request(
               ^^^^^^^^^^^^^^^^^^^
  File "/home/soham/projects/Cloud-Copy/.venv/lib/python3.12/site-packages/urllib3/connectionpool.py", line 493, in _make_request
    conn.request(
  File "/home/soham/projects/Cloud-Copy/.venv/lib/python3.12/site-packages/botocore/awsrequest.py", line 96, in request
    rval = super().request(method, url, body, headers, *args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/soham/projects/Cloud-Copy/.venv/lib/python3.12/site-packages/urllib3/connection.py", line 514, in request
    self.send(chunk)
  File "/home/soham/projects/Cloud-Copy/.venv/lib/python3.12/site-packages/botocore/awsrequest.py", line 223, in send
    return super().send(str)
           ^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/http/client.py", line 1084, in send
    self.sock.sendall(data)
  File "/usr/lib/python3.12/ssl.py", line 1211, in sendall
    v = self.send(byte_view[count:])
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/ssl.py", line 1180, in send
    return self._sslobj.write(data)
           ^^^^^^^^^^^^^^^^^^^^^^^^
ssl.SSLEOFError: EOF occurred in violation of protocol (_ssl.c:2417)

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/home/soham/projects/Cloud-Copy/.venv/lib/python3.12/site-packages/botocore/httpsession.py", line 509, in send
    urllib_response = conn.urlopen(
                      ^^^^^^^^^^^^^
  File "/home/soham/projects/Cloud-Copy/.venv/lib/python3.12/site-packages/urllib3/connectionpool.py", line 842, in urlopen
    retries = retries.increment(
              ^^^^^^^^^^^^^^^^^^
  File "/home/soham/projects/Cloud-Copy/.venv/lib/python3.12/site-packages/urllib3/util/retry.py", line 473, in increment
    raise reraise(type(error), error, _stacktrace)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/soham/projects/Cloud-Copy/.venv/lib/python3.12/site-packages/urllib3/util/util.py", line 38, in reraise
    raise value.with_traceback(tb)
  File "/home/soham/projects/Cloud-Copy/.venv/lib/python3.12/site-packages/urllib3/connectionpool.py", line 788, in urlopen
    response = self._make_request(
               ^^^^^^^^^^^^^^^^^^^
  File "/home/soham/projects/Cloud-Copy/.venv/lib/python3.12/site-packages/urllib3/connectionpool.py", line 493, in _make_request
    conn.request(
  File "/home/soham/projects/Cloud-Copy/.venv/lib/python3.12/site-packages/botocore/awsrequest.py", line 96, in request
    rval = super().request(method, url, body, headers, *args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/soham/projects/Cloud-Copy/.venv/lib/python3.12/site-packages/urllib3/connection.py", line 514, in request
    self.send(chunk)
  File "/home/soham/projects/Cloud-Copy/.venv/lib/python3.12/site-packages/botocore/awsrequest.py", line 223, in send
    return super().send(str)
           ^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/http/client.py", line 1084, in send
    self.sock.sendall(data)
  File "/usr/lib/python3.12/ssl.py", line 1211, in sendall
    v = self.send(byte_view[count:])
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/ssl.py", line 1180, in send
    return self._sslobj.write(data)
           ^^^^^^^^^^^^^^^^^^^^^^^^
urllib3.exceptions.SSLError: EOF occurred in violation of protocol (_ssl.c:2417)

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/home/soham/projects/Cloud-Copy/app/services/transfer_service.py", line 299, in _worker_loop
    await self._run_job(job)
  File "/home/soham/projects/Cloud-Copy/app/services/transfer_service.py", line 374, in _run_job
    await self._transfer_folder(
  File "/home/soham/projects/Cloud-Copy/app/services/transfer_service.py", line 462, in _transfer_folder
    await self._transfer_file(
  File "/home/soham/projects/Cloud-Copy/app/services/transfer_service.py", line 539, in _transfer_file
    uploaded = await self._await_step(
               ^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/soham/projects/Cloud-Copy/app/services/transfer_service.py", line 160, in _await_step
    return task.result()
           ^^^^^^^^^^^^^
  File "/home/soham/projects/Cloud-Copy/app/services/pikpak_client.py", line 447, in upload_from_path
    return await self._upload_with_type(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/soham/projects/Cloud-Copy/app/services/pikpak_client.py", line 559, in _upload_with_type
    return await self._upload_with_type(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/soham/projects/Cloud-Copy/app/services/pikpak_client.py", line 550, in _upload_with_type
    await self._upload_s3(local_path, params, on_progress)
  File "/home/soham/projects/Cloud-Copy/app/services/pikpak_client.py", line 685, in _upload_s3
    await asyncio.to_thread(_put)
  File "/usr/lib/python3.12/asyncio/threads.py", line 25, in to_thread
    return await loop.run_in_executor(None, func_call)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/concurrent/futures/thread.py", line 58, in run
    result = self.fn(*self.args, **self.kwargs)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/soham/projects/Cloud-Copy/app/services/pikpak_client.py", line 672, in _put
    raise last_exc
  File "/home/soham/projects/Cloud-Copy/app/services/pikpak_client.py", line 651, in _put
    s3.put_object(
  File "/home/soham/projects/Cloud-Copy/.venv/lib/python3.12/site-packages/botocore/client.py", line 606, in _api_call
    return self._make_api_call(operation_name, kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/soham/projects/Cloud-Copy/.venv/lib/python3.12/site-packages/botocore/context.py", line 123, in wrapper
    return func(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/home/soham/projects/Cloud-Copy/.venv/lib/python3.12/site-packages/botocore/client.py", line 1076, in _make_api_call
    http, parsed_response = self._make_request(
                            ^^^^^^^^^^^^^^^^^^^
  File "/home/soham/projects/Cloud-Copy/.venv/lib/python3.12/site-packages/botocore/client.py", line 1100, in _make_request
    return self._endpoint.make_request(operation_model, request_dict)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/soham/projects/Cloud-Copy/.venv/lib/python3.12/site-packages/botocore/endpoint.py", line 119, in make_request
    return self._send_request(request_dict, operation_model)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/soham/projects/Cloud-Copy/.venv/lib/python3.12/site-packages/botocore/endpoint.py", line 231, in _send_request
    raise exception
  File "/home/soham/projects/Cloud-Copy/.venv/lib/python3.12/site-packages/botocore/endpoint.py", line 281, in _do_get_response
    http_response = self._send(request)
                    ^^^^^^^^^^^^^^^^^^^
  File "/home/soham/projects/Cloud-Copy/.venv/lib/python3.12/site-packages/botocore/endpoint.py", line 385, in _send
    return self.http_session.send(request)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/soham/projects/Cloud-Copy/.venv/lib/python3.12/site-packages/botocore/httpsession.py", line 537, in send
    raise SSLError(endpoint_url=request.url, error=e)
botocore.exceptions.SSLError: SSL validation failed for https://upload-a10b.mypikpak.com/vip-lixian-07/upload_tmp/E5D772F6C0BEA65D996D88B5CE3E36ECA8A9D644_1788780410962676188 EOF occurred in violation of protocol (_ssl.c:2417)

