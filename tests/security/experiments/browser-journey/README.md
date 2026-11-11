# C2 browser journey prerequisite spike

The pinned image contains Firefox but no `geckodriver`. The check records that exact dependency
instead of substituting a spider or the operator's personal browser for a reproducible click
journey.

```sh
bash tests/security/experiments/browser-journey/run.sh --out /tmp/browser-prerequisites
```

Status stays `BLOCKED` until a matching driver/browser pair is pinned in the image. The next
spike must proxy a fixed open/click/wait journey through ZAP and prove both UI terminal state
and the `/private-data` history marker; the no-click control must remain missing evidence.
