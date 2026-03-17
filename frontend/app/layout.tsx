import "./globals.css";
import { Fraunces, Manrope } from "next/font/google";

const fraunces = Fraunces({
  subsets: ["latin"],
  weight: ["400", "600", "700"],
  variable: "--font-display"
});

const manrope = Manrope({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-sans"
});

export const metadata = {
  title: "VKORNI | Генератор биографий",
  description: "Создавайте литературные профили, показывайте фото и отправляйте на vkorni.ru."
};

export default function RootLayout({
  children
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="cs" className={`${fraunces.variable} ${manrope.variable}`}>
      <body className="bg-noise">
        {children}
      </body>
    </html>
  );
}
