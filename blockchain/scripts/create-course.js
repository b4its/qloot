// Create a course on the OPC contract.
//   COURSE_ID=1001 REWARD=500 BADGE_ID=1 ACTIVE=true make blockchain-create-course
const { ethers } = require("hardhat");
const lib = require("./_lib");

async function main() {
  const courseId = process.env.COURSE_ID;
  if (!courseId) throw new Error("COURSE_ID is required");
  const reward = BigInt(process.env.REWARD || "0");
  const badgeId = Number(process.env.BADGE_ID || "0");
  const active = (process.env.ACTIVE || "true") !== "false";

  const opc = await lib.getDeployedContract();
  const tx = await opc.createCourse(courseId, reward, badgeId, active);
  console.log(`createCourse tx: ${tx.hash}`);
  await tx.wait();
  console.log(`course ${courseId}: reward=${reward} badge=${badgeId} active=${active}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
