# CellX RDP Marketing Site

English promotional website for the Rapid Development Platform. It is built as a static site so it can be deployed easily on AWS Lightsail with Nginx or Apache.

## Local preview

```powershell
python -m http.server 5180
```

Open:

```text
http://127.0.0.1:5180/index.html
```

## Lightsail deployment with Nginx

1. Create an Ubuntu Lightsail instance.
2. SSH into the instance.
3. Install Nginx:

```bash
sudo apt update
sudo apt install -y nginx
```

4. Upload this folder to the server:

```bash
scp -r rdp-marketing-site ubuntu@YOUR_LIGHTSAIL_IP:/tmp/
```

5. Move the site into the web root:

```bash
sudo mkdir -p /var/www/rdp-marketing-site
sudo cp -r /tmp/rdp-marketing-site/* /var/www/rdp-marketing-site/
sudo chown -R www-data:www-data /var/www/rdp-marketing-site
```

6. Install the Nginx config:

```bash
sudo cp /var/www/rdp-marketing-site/nginx.conf /etc/nginx/sites-available/rdp-marketing-site
sudo ln -s /etc/nginx/sites-available/rdp-marketing-site /etc/nginx/sites-enabled/rdp-marketing-site
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

7. Visit:

```text
http://YOUR_LIGHTSAIL_IP
```

## Payment integration notes

The current checkout is a front-end payment experience in demo mode. For real payment collection:

- Stripe: create a Lightsail backend endpoint that creates a Stripe Checkout Session, then redirect users to the returned session URL.
- PayPal: create a backend endpoint using the PayPal Orders API, then approve and capture the order.
- Bank card: handle cards through Stripe Elements or Stripe Checkout. Do not collect raw card data on your own server unless you are PCI compliant.

Recommended production pattern:

```text
Static website -> Lightsail backend API -> Stripe / PayPal provider -> webhook -> activate membership
```

Do not put Stripe secret keys, PayPal secrets, or bank-card processing secrets in `app.js`.
