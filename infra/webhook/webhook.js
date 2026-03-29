const http = require("http");
const crypto = require("crypto");
const { exec } = require("child_process");

const SECRET = process.env.WEBHOOK_SECRET || "очень_секретная_строка";
const REPO_PATH = "/var/www/fa-skins-tokenization";
const BRANCH = "main";

function isValidSignature(signature, body) {
  if (!signature) return false;
  const hmac = crypto.createHmac("sha256", SECRET);
  const digest = "sha256=" + hmac.update(body).digest("hex");
  return crypto.timingSafeEqual(Buffer.from(digest), Buffer.from(signature));
}

const server = http.createServer((req, res) => {
  if (req.method !== "POST") {
    res.statusCode = 405;
    return res.end("Method Not Allowed");
  }

  let chunks = [];
  req.on("data", chunk => chunks.push(chunk));
  req.on("end", () => {
    const body = Buffer.concat(chunks);
    const sigHeader = req.headers["x-hub-signature-256"];

    if (!isValidSignature(sigHeader, body)) {
      res.statusCode = 403;
      return res.end("Invalid signature");
    }

    let payload;
    try {
      payload = JSON.parse(body.toString("utf8"));
    } catch (e) {
      res.statusCode = 400;
      return res.end("Bad JSON");
    }

    if (payload.ref === `refs/heads/${BRANCH}`) {
      console.log(`[${new Date().toISOString()}] Push to ${BRANCH} — deploying...`);

      // git pull + deploy script
      const cmd = `cd ${REPO_PATH} && git pull origin ${BRANCH} && bash deploy.sh >> /var/log/fa-skins-deploy.log 2>&1`;
      exec(cmd, (err, stdout, stderr) => {
        if (err) console.error("Deploy error:", err);
        if (stdout) console.log("stdout:", stdout);
        if (stderr) console.error("stderr:", stderr);
      });
    }

    res.statusCode = 200;
    res.end("OK");
  });
});

const PORT = 8080;
server.listen(PORT, () => {
  console.log(`Webhook listening on port ${PORT}`);
});
