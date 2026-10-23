# AURA guardian-circle AWS setup

This folder contains the remote-sharing backend and infrastructure template. It is not connected to an AWS account yet. Deploying provisions real AWS resources and may incur charges. The API uses Cognito sign-in, an API Gateway JWT authorizer, and DynamoDB; the guardian page is hosted privately in S3 behind CloudFront.

## 1. Deploy the stack

Install and configure the AWS CLI and AWS SAM CLI for your own AWS account. From this folder:

```sh
sam build
sam deploy --guided
```

Choose a new stack name, your AWS region, and a globally unique lowercase Cognito domain prefix. Keep `WebOrigin` as `http://localhost:8006` if AURA will run at that local address. Review the change set and AWS costs before confirming deployment. Do not commit AWS credentials or access keys.

When deployment finishes, open the stack's **Outputs** in the AWS CloudFormation console. Copy these outputs: `ApiUrl`, `CognitoHostedUiDomain`, `UserPoolClientId`, `GuardianWebsiteUrl`, and `WebBucketName`.

## 2. Configure AURA and the guardian page

Edit `../remote-config.js` with the public outputs:

```js
window.AURA_REMOTE_CONFIG = {
  apiBase: "PASTE_ApiUrl",
  cognitoDomain: "PASTE_CognitoHostedUiDomain",
  clientId: "PASTE_UserPoolClientId",
  scope: "openid email profile aura/circle.share"
};
```

These Cognito/API identifiers are public client settings, not AWS credentials. Use the same file for AURA on localhost and the guardian portal. Upload the guardian portal files to the bucket whose name is `WebBucketName`:

```sh
aws s3 cp guardian.html s3://PASTE_WebBucketName/guardian.html --content-type text/html
aws s3 cp ../guardian-cloud.js s3://PASTE_WebBucketName/guardian-cloud.js --content-type application/javascript
aws s3 cp ../remote-config.js s3://PASTE_WebBucketName/remote-config.js --content-type application/javascript
```

Open `GuardianWebsiteUrl` and sign in. For the patient side, start AURA at the configured origin:

```sh
cd ..
PORT=8006 python3 server.py
```

Then open <http://localhost:8006>. `remote-config.js` is shared by both pages, and the deployed API accepts the CloudFront guardian page plus the configured local origin.

## 3. Pair the accounts

1. The patient signs in, creates a circle, and creates a one-time invite.
2. The patient sends the invite code to the intended guardian through a channel they choose. AURA does not send the invite automatically.
3. The guardian opens `GuardianWebsiteUrl`, signs in with a verified email, enters the code, and requests access.
4. The patient checks the verified email shown in the member list and approves that guardian.
5. The patient selects the exact fields to share, grants browser location permission if location is selected, and starts sharing.
6. The guardian keeps the page open. It polls every five seconds while the patient app uploads every five seconds. Either person can sign out; the patient can stop sharing at any time.

Only the latest reading is kept, with a three-minute DynamoDB TTL. The app marks a reading older than 45 seconds as stale and hides it. When sharing stops, the API deletes the latest reading. Server logs are configured for seven days and do not intentionally include request bodies, tokens, health values, or precise coordinates.

## Limits

- This prototype has no emergency detection, medical diagnosis, SOS dispatch, SMS, or ambulance connection.
- Browser wearable access only works for standard BLE services supported by the device and browser. Apple Watch data needs the separate iPhone/HealthKit host app described in `../ios/README.md`.
- The iOS bridge source is not a compiled or signed app. It needs a host app, HealthKit and location configuration, Cognito token provider, and testing on a physical iPhone/watch.
- Keep the AURA laptop page open for its browser-based location and BLE uploads. Background delivery is not guaranteed.
- The DynamoDB table uses `DeletionPolicy: Retain`; deleting the CloudFormation stack does not automatically delete that table. Review/delete retained data intentionally in AWS if you retire the project.
- Deploy only to an account you control. Add a custom domain, stronger operational monitoring, security review, and accessibility/medical safety review before any real-world use.
