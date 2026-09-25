# CDN Xray API preparation

`prepare_mobile_api.py` creates a private candidate JSON file. It does not
change the active `yandex-cdn-test.json` or restart either Xray service.

It adds `HandlerService` on `127.0.0.1:10086` using Xray's simplified API
configuration, leaving the CDN inbound and existing clients untouched.

On the VPN node, validate the candidate with its installed Xray binary:

```sh
sudo python3 prepare_mobile_api.py \
  /usr/local/etc/xray/yandex-cdn-test.json \
  /root/yandex-cdn-api-candidate.json
sudo /usr/local/bin/xray run -test -config /root/yandex-cdn-api-candidate.json
```

The candidate contains VLESS credentials and must not be pasted into chat or
placed in Git. A successful `-test` only proves the JSON is accepted; a
separate change is needed to deploy it, persist Mobile users, and provision
them from the backend. Do not activate Mobile plans at this stage.
