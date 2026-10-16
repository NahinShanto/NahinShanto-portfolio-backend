import ipaddress


def get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    ip = forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")
    try:
        ipaddress.ip_address(ip)
    except (ValueError, TypeError):
        return None
    return ip