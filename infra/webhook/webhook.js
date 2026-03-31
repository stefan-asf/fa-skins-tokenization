const http = require("http");
const crypto = require("crypto");
const { execSync } = require("child_process");

const PORT = 8080;
const SECRET = process.env.WEBHOOK_SECRET || "";
const REPO = "/var/www/fa-skins-tokenization";

function verifySignature(body, signature) {
  if (!SECRET) return true;
  const hmac = crypto.createHmac("sha256", SECRET);
  hmac.update(body);
  const expected = "sha256=" + hmac.digest("hex");
  try {
    return crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(signature));
  } catch {
    return false;
  }
}

const server = http.createServer((req, res) => {
  if (req.method !== "POST") {
    res.writeHead(405);
    res.end("Method Not Allowed");
    return;
  }

  let body = "";
  req.on("data", (chunk) => { body += chunk; });
  req.on("end", () => {
    const signature = req.headers["x-hub-signature-256"] || "";
    if (!verifySignature(body, signature)) {
      console.error("[webhook] Invalid signature");
      res.writeHead(403);
      res.end("Forbidden");
      return;
    }

    res.writeHead(200);
    res.end("OK");

    console.log("[webhook] Received push, deploying...");
    try {
      execSync(`cd ${REPO} && git pull --ff-only`, { stdio: "inherit" });
      execSync(`bash ${REPO}/deploy.sh`, { stdio: "inherit" });
      console.log("[webhook] Deploy done");
    } catch (err) {
      console.error("[webhook] Deploy failed:", err.message);
    }
  });
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`[webhook] Listening on 127.0.0.1:${PORT}`);
});
