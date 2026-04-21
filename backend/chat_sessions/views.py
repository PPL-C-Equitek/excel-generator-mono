from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from authentication.permissions import IsVerifiedUser
from chat_sessions.serializers import (
    SessionDetailSerializer,
    SessionListItemSerializer,
    SessionTitleUpdateSerializer,
)
from chat_sessions.services import (
    delete_session,
    get_session_for_user,
    list_sessions_for_user,
    update_session_title,
)


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsVerifiedUser])
def session_list(request):
    sessions = list(list_sessions_for_user(request.user))
    serializer = SessionListItemSerializer(sessions, many=True)
    return Response(
        {
            "count": len(sessions),
            "results": serializer.data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsVerifiedUser])
def session_detail(request, session_id):
    session = get_session_for_user(request.user, session_id)
    if session is None:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    return Response(SessionDetailSerializer(session).data, status=status.HTTP_200_OK)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated, IsVerifiedUser])
def session_update(request, session_id):
    session = get_session_for_user(request.user, session_id)
    if session is None:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    serializer = SessionTitleUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    updated_session = update_session_title(session, serializer.validated_data["title"])
    return Response(
        SessionListItemSerializer(updated_session).data,
        status=status.HTTP_200_OK,
    )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated, IsVerifiedUser])
def session_delete(request, session_id):
    session = get_session_for_user(request.user, session_id)
    if session is None:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    delete_session(session)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated, IsVerifiedUser])
def session_resource(request, session_id):
    if request.method == "GET":
        return session_detail(request, session_id)
    if request.method == "PATCH":
        return session_update(request, session_id)
    return session_delete(request, session_id)
