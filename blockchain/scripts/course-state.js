// Show a user's course / XP / badge state.
//   ADDRESS=0x.. COURSE_ID=1001 make blockchain-course-state
const { ethers } = require("hardhat");
const lib = require("./_lib");

async function main() {
  const address = process.env.ADDRESS;
  const courseId = process.env.COURSE_ID;
  if (!address || !ethers.isAddress(address)) throw new Error("ADDRESS is required");
  const opc = await lib.getDeployedContract();
  console.log(`address     : ${address}`);
  console.log(`OPC balance : ${await opc.balanceOf(address, 0)}`);
  console.log(`xp / level  : ${await opc.xp(address)} / ${await opc.level(address)}`);
  console.log(`badges      : ${await opc.userBadgeCount(address)}`);
  if (courseId) {
    console.log(
      `course ${courseId}: enrolled=${await opc.enrolled(
        address,
        courseId
      )} completed=${await opc.completed(address, courseId)}`
    );
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
