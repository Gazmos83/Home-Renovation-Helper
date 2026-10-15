# RunPod setup for render offload

In RunPod pod mode, the app creates a GPU pod only after you approve a `final` render. It deletes the pod once it has been idle for the idle time (10 minutes by default). Blender, the SSH keys and a few system packages live on a small **network volume**, so every new pod starts ready to use. You set that volume up once, by hand, with `scripts/runpod/setup_volume.sh`. The app never runs this script.

## What it costs

These are RunPod's list prices as of 2026-10-15; check them before you start.

- **GPU:** Secure Cloud only, because network volumes exist only there. An RTX 4090 costs $0.89 per hour (Secure Cloud catalog read, 2026-10-15) while a pod exists, billed for start-up, rendering and the idle time.
- **Volume:** $0.07 per GB per month, all the time. Runpod's smallest volume is 10 GB, about $0.70 a month.

## 1. Account and spending

The app has no spending limit of its own. Your RunPod account is the backstop.

1. Load a small **prepaid balance**, for example $10–20, and leave **auto-pay off**. Then the most you can spend is what you loaded.
2. Set a **low-balance email alert** at about $3–5.
3. Keep at least about $1 in the account. RunPod creates a pod only if the balance covers an hour of it, so remote finals fail to start below that.
4. If the balance reaches $0, RunPod stops running pods. The volume keeps billing, and if the balance stays at zero it may eventually be deleted, which would remove the Blender install.
5. Create an **API key** (Settings → API Keys). It goes into `.env` as `RENDER_OFFLOAD_RUNPOD_API_KEY` and nowhere else.

## 2. The network volume

1. Pick a **data centre that has good stock of your GPU** (for example the RTX 4090). Every pod is created in the volume's data centre. If that GPU is sold out there, the final is refused with "no … is free on RunPod right now". Moving later means making a new volume.
2. Create a network volume of **10 GB**, Runpod's minimum, there (Storage → Network Volumes). Note its id.

## 3. Prepare the volume once

1. Choose the image, pinned to a tag (never `latest`), for example `runpod/base:<tag>`. Use the **same image** here and in `RENDER_OFFLOAD_RUNPOD_IMAGE`, because the packages saved on the volume are the ones that image lacks.
2. Deploy a temporary pod with that image and the network volume attached at `/workspace`. The cheapest GPU in that data centre is enough.
3. On the laptop, print your public key: `cat ~/.ssh/id_ed25519.pub` (make one with `ssh-keygen -t ed25519` if needed).
4. In the pod's web terminal, copy in `scripts/runpod/setup_volume.sh` and run:

   ```bash
   bash setup_volume.sh "ssh-ed25519 AAAA… you@laptop"
   ```

   It:
   - saves the system packages Blender and `sshd` need that the image lacks into `/workspace/hra/debs`;
   - downloads Blender 5.2.1, checks its SHA-256 against blender.org, unpacks it to `/workspace/blender-5.2.1-linux-x64`, and checks that it starts headless;
   - creates the pod SSH host key on the volume and stores your public key as the only authorised key;
   - prints a line starting with `hra-render-pod ssh-ed25519 …`.
5. Put that printed line into a known-hosts file on the laptop, for example `~/.ssh/hra_known_hosts`. Every pod presents this same key under the name `hra-render-pod`, so host-key checking stays strict even though each pod has a new address.
6. **Delete the temporary pod.** The volume keeps everything.

## 4. Configure the app

In `.env` (leave `RENDER_OFFLOAD_HOST` unset; the two modes cannot be combined):

```
RENDER_OFFLOAD_RUNPOD_API_KEY=…
RENDER_OFFLOAD_RUNPOD_NETWORK_VOLUME_ID=<volume id>
RENDER_OFFLOAD_RUNPOD_GPU_TYPE=NVIDIA GeForce RTX 4090
RENDER_OFFLOAD_RUNPOD_IMAGE=runpod/base:<tag>
RENDER_OFFLOAD_USER=root
RENDER_OFFLOAD_KEY_PATH=/home/<you>/.ssh/id_ed25519
RENDER_OFFLOAD_KNOWN_HOSTS_PATH=/home/<you>/.ssh/hra_known_hosts
RENDER_OFFLOAD_BLENDER=/workspace/blender-5.2.1-linux-x64/blender
RENDER_OFFLOAD_CYCLES_DEVICE=OPTIX
```

Restart the backend. The startup summary says `render_offload: RunPod pod (<GPU type>)`.

## 5. First run

On the developer panel's **Render Offload** tab:

1. **Test the connection.** With no pod running, this asks RunPod about the key and the volume only, and starts nothing.
2. **Run the remote benchmark.** This creates the first pod, measures its start-up time and one Cycles frame, and leaves the pod running for the idle time.
3. Switch **Final renders** to *On the render server*.

After that, the estimate for a remote final includes the start-up time while no pod is running. **Render pod** shows when an idle pod will be deleted, and **Delete pod now** ends it early. **Pod sessions** lists each pod's lifetime and cost at RunPod's hourly price.

## When something goes wrong

- **"the render pod's host key does not match"**: the known-hosts line is not the volume's key. Re-run the script and copy the printed line again.
- **"the render pod runs Blender …"** or **"could not run Blender"**: re-run the script on a pod with the configured image.
- **"Delete failed" on the panel**: the app retries every minute. Check the RunPod console and delete the `hra-render` pod there if needed. The app also deletes any leftover `hra-render` pod when it starts.
- **Blender upgrade**: change the version in the script and in the app's pinned version together. That is a code change, not a setting.
