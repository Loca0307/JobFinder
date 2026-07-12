
/** @type {import('next').NextConfig} */
const nextConfig = {
    // To be able to export the static part of the 
    // website on the S3 bucket to serve it on cloudfront 
  output: "export",
  trailingSlash: true
};

export default nextConfig;