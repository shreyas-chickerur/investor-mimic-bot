/** @type {import('next').NextConfig} */
const nextConfig = {
  env: {
    NEXT_PUBLIC_GH_REPO:
      process.env.NEXT_PUBLIC_GH_REPO ?? "shreyaschickerur/investor-mimic-bot",
  },
};

export default nextConfig;
