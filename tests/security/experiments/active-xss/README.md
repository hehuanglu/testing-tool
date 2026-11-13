# B3 one-rule active XSS experiment

This disposable fixture enables only native active rule `40012` at low strength/threshold.
The active request header witness, a successful response, and the native alert instance for
parameter `q` are evaluated separately. The result records the ZAP version read from the native
report alongside the rule ID.

```sh
bash tests/security/experiments/active-xss/run.sh --mode vulnerable --out /tmp/xss-vulnerable
bash tests/security/experiments/active-xss/run.sh --mode fixed --out /tmp/xss-fixed
bash tests/security/experiments/active-xss/run.sh --mode auth-lost --out /tmp/xss-auth-lost
```

The experiment is not part of PR defaults and remains experimental until detector stability,
all three controls, clean artifacts and a manual GitHub run are recorded.
